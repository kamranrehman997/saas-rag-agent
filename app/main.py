import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from anthropic import Anthropic

from app.config import settings
from app.services.scraper import WebsiteScraper
from app.services.analyzer import GapAnalyzerService, KnowledgeGapAnalysis
from app.services.vector_store import VectorStoreService
from app.services.ticket_store import TicketStore

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Services
scraper = WebsiteScraper()
analyzer = GapAnalyzerService()
vector_store = VectorStoreService()
ticket_store = TicketStore()
anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# Request Models
class AnalyzeRequest(BaseModel):
    business_name: str
    website_url: HttpUrl

class FinalizeRequest(BaseModel):
    tenant_id: str | None = None
    business_name: str
    scraped_pages: dict[str, str]
    answers: dict[str, str]

class ChatRequest(BaseModel):
    message: str
    customer_email: str | None = None

class ResolveTicketRequest(BaseModel):
    human_answer: str


@app.post("/api/onboard/analyze", response_model=KnowledgeGapAnalysis)
async def analyze_onboarding(payload: AnalyzeRequest):
    """Step 2 & 3: Scrape the business website and analyze knowledge gaps."""
    scraped_data = await scraper.scrape_domain(str(payload.website_url))
    if not scraped_data:
        raise HTTPException(status_code=400, detail="Could not retrieve any content from the specified URL.")
    
    analysis = await analyzer.analyze_scraped_content(payload.business_name, scraped_data)
    return analysis


@app.post("/api/onboard/finalize")
async def finalize_onboarding(payload: FinalizeRequest):
    """Step 4: Compile scraped data and owner answers into ChromaDB and output embed tag."""
    tenant_id = payload.tenant_id or str(uuid.uuid4())
    
    vector_store.ingest_onboarding_data(
        tenant_id=tenant_id,
        scraped_pages=payload.scraped_pages,
        owner_answers=payload.answers
    )
    
    embed_script = f"""<script src="http://localhost:8000/widget.js" data-tenant-id="{tenant_id}"></script>"""
    
    return {
        "status": "success",
        "tenant_id": tenant_id,
        "embed_tag": embed_script
    }


@app.post("/api/chat/{tenant_id}")
async def chat_runtime(tenant_id: str, payload: ChatRequest):
    """Step 5: Runtime RAG endpoint with Anthropic Tool-Calling for human support escalation."""
    # 1. Retrieve relevant context from ChromaDB
    retrieved_docs = vector_store.similarity_search(tenant_id, payload.message, n_results=4)
    context_text = "\n\n".join(retrieved_docs) if retrieved_docs else "No specific policy documentation found."

    # 2. Define tool for human escalation
    tools = [
        {
            "name": "escalate_to_human",
            "description": "Escalate the customer's issue to human support when the knowledge base lacks sufficient info, or when the user explicitly asks for a human.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Why escalation is required."},
                    "summary": {"type": "string", "description": "Summary of the customer query and issue."}
                },
                "required": ["reason", "summary"]
            }
        }
    ]

    system_prompt = f"""
    You are a helpful, professional customer support AI assistant for this business.
    Answer customer questions strictly based on the provided Knowledge Base Context. 
    If the context does not contain the answer, or if the customer is frustrated, angry, or asks for a refund/special exception, you MUST call the `escalate_to_human` tool. Do not guess policy details.
    
    Knowledge Base Context:
    {context_text}
    """

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5",  # Using the working Haiku 4.5 alias
        max_tokens=600,
        system=system_prompt,
        tools=tools,
        messages=[{"role": "user", "content": payload.message}]
    )

    # Check if model invoked tool calling (escalation)
    escalation_triggered = False
    escalation_details = None

    for content_block in response.content:
        if content_block.type == "tool_use":
            escalation_triggered = True
            escalation_details = content_block.input

    assistant_reply = ""
    for content_block in response.content:
        if content_block.type == "text":
            assistant_reply += content_block.text

    ticket = None
    if escalation_triggered:
        reason = (escalation_details or {}).get("reason") or "Customer query requires human support."
        ticket = ticket_store.create_ticket(
            tenant_id=tenant_id,
            customer_question=payload.message,
            customer_email=payload.customer_email,
            reason=reason,
        )

    return {
        "reply": assistant_reply or "I have escalated your query to our human support team. Someone will email you shortly.",
        "escalated": escalation_triggered,
        "escalation_data": escalation_details,
        "ticket": ticket,
    }


@app.get("/api/tickets/{tenant_id}")
async def list_open_tickets(tenant_id: str):
    """List open escalated tickets for a tenant."""
    return {"tickets": ticket_store.get_open_tickets(tenant_id)}


@app.post("/api/tickets/{tenant_id}/{ticket_id}/resolve")
async def resolve_ticket(tenant_id: str, ticket_id: str, payload: ResolveTicketRequest):
    """Mark an escalated ticket resolved, close it, and ingest the learned QA pair into ChromaDB."""
    ticket = ticket_store.resolve_ticket(tenant_id, ticket_id, payload.human_answer)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Open ticket not found for this tenant.")

    # Format as a crisp Q&A rule and store in ChromaDB for future self-learning
    learned_entry = (
        f"Verified Support Policy / Pricing Rule:\n"
        f"Customer Question: {ticket['customer_question']}\n"
        f"Official Answer: {payload.human_answer}"
    )

    vector_store.ingest_onboarding_data(
        tenant_id=tenant_id,
        scraped_pages={},
        owner_answers={ticket["customer_question"]: learned_entry}
    )

    return {
        "status": "learned_and_resolved",
        "ticket_id": ticket_id,
        "indexed_knowledge": learned_entry
    }