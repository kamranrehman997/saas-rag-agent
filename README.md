\# Multi-Tenant RAG SaaS Agent for E-Commerce



An end-to-end, production-ready Retrieval-Augmented Generation (RAG) SaaS backend and embeddable frontend chat widget designed for e-commerce stores. The platform automates store onboarding via web scraping and LLM-driven knowledge gap auditing, isolates tenant vector data, and features a human-in-the-loop active learning pipeline that converts resolved support tickets into permanent RAG knowledge.



\---



\## Key Features



\* \*\*Automated Onboarding \& Gap Auditing:\*\* Scrapes target e-commerce websites, extracts product and policy content, and uses Claude Haiku 4.5 to identify missing operational details (e.g., return windows, shipping surcharges, assembly pricing) and generate targeted follow-up questions.

\* \*\*Multi-Tenant Vector Isolation:\*\* Partitions embeddings inside ChromaDB by `tenant\_id` so multiple stores operate concurrently on shared infrastructure with strict data separation.

\* \*\*Tool-Calling Escalation Engine:\*\* Equips the chat agent with an `escalate\_to\_human` tool. Instead of hallucinating unknown policies, the bot gracefully escalates ambiguous or missing queries to a persistent ticket queue.

\* \*\*Human-in-the-Loop Active Learning:\*\* When an operator resolves an open ticket via the API, the Q\&A pair is automatically formatted into a verified policy document and ingested into ChromaDB—allowing the bot to answer similar future queries autonomously.

\* \*\*Embeddable JavaScript Widget:\*\* Includes a lightweight, self-contained `widget.js` script served by FastAPI that injects a floating support chat window onto any storefront via a single `<script>` tag.



\---



\## Tech Stack



\* \*\*Backend Framework:\*\* Python, FastAPI, Uvicorn, Pydantic

\* \*\*LLM \& Tool Calling:\*\* Anthropic API (`claude-haiku-4-5`)

\* \*\*Vector Database:\*\* ChromaDB (persistent local storage with tenant metadata filtering)

\* \*\*Web Scraping:\*\* BeautifulSoup4, HTTPX / Requests

\* \*\*Frontend Widget:\*\* Vanilla JavaScript, CSS3 (injected dynamically)

\* \*\*Containerization:\*\* Docker, Docker Compose



\---



\## System Architecture



```text

1\. Onboarding \& Gap Audit

&#x20;  \[Store URL] ──▶ Web Scraper ──▶ LLM Gap Analyzer ──▶ Missing Policy Questions



2\. Knowledge Base Ingestion

&#x20;  \[Scraped Pages + Owner Q\&As] ──▶ Chunking \& Embeddings ──▶ ChromaDB (tenant\_id partition)



3\. Customer Chat \& Active Learning Loop

&#x20;  \[Storefront Widget] ──▶ POST /api/chat/{tenant\_id} ──▶ ChromaDB Retrieval + Claude

&#x20;                                   │

&#x20;                      (If policy missing / uncertain)

&#x20;                                   ▼

&#x20;                       \[escalate\_to\_human Tool]

&#x20;                                   │

&#x20;                                   ▼

&#x20;                      Persistent TicketStore (JSON)

&#x20;                                   │

&#x20;                      (Human resolves via API)

&#x20;                                   ▼

&#x20;            Auto-Ingested into ChromaDB as Verified Policy





\------------------------------------------------------------------------------------------------



Project structure



saas-rag-onboarding/

├── app/

│   ├── main.py              # FastAPI application, endpoints, and static widget routing

│   ├── rag\_engine.py        # ChromaDB client, tenant ingestion, and semantic retrieval

│   ├── agent.py             # Anthropic Claude integration and tool-calling logic

│   ├── scraper.py           # Website crawler and LLM gap-analysis pipeline

│   ├── ticket\_store.py      # Persistent JSON store for escalated support tickets

│   └── static/

│       └── widget.js        # Self-contained floating chat widget script

├── data/                    # Persistent ticket logs (gitignored)

├── chroma\_db/               # Persistent vector embeddings (gitignored)

├── docker-compose.yml       # Container orchestration

├── Dockerfile               # Python environment setup

├── requirements.txt         # Project dependencies

├── .env.example             # Environment variable template

└── README.md



\---------------------------------------------------------------------------------------------



Getting Started

Prerequisites

Docker \& Docker Compose installed



An Anthropic API Key



Installation \& Running Locally

1. Clone the repository:

git clone \[https://github.com/kamranrehman997/saas-rag-agent.git](https://github.com/kamranrehman997/saas-rag-agent.git)

cd saas-rag-agent



2.Configure environment variables:

Create a .env file in the root directory and add your Anthropic API key: 

ANTHROPIC\_API\_KEY=your\_anthropic\_api\_key\_here



3\. Build and start the container:
docker-compose up --build



The API and interactive Swagger documentation will be available at http://localhost:8000/docs.



\----------------------------------------------------------------------------------------------



API Workflow \& Usage

1\. Analyze a Storefront (POST /api/onboard/analyze)

Scrapes the target store URL and returns a summary of captured data alongside identified policy gaps.



{

&#x20; "url": "\[https://aurafurniture.uk](https://aurafurniture.uk)"

}





2\. Finalize Tenant Knowledge Base (POST /api/onboard/finalize)

Ingests scraped pages and owner-provided answers into an isolated tenant\_id namespace in ChromaDB.

{

&#x20; "tenant\_id": "aurafurniture",

&#x20; "business\_name": "Aura Furniture",

&#x20; "scraped\_pages": {

&#x20;   "catalog": "Sliding wardrobes with 0% APR instalments and 3-7 day UK Mainland delivery..."

&#x20; },

&#x20; "answers": {

&#x20;   "What is your return policy?": "14-day returns from delivery in original unopened packaging."

&#x20; }

}



3\. Customer Chat (POST /api/chat/{tenant\_id})

Queries the tenant's RAG knowledge base and automatically escalates if information is missing.



JSON

{

&#x20; "message": "Do you offer upstairs delivery and how much does it cost?"

}



4\. View \& Resolve Escalated Tickets

List Open Tickets: GET /api/tickets/{tenant\_id}



Resolve \& Train Bot: POST /api/tickets/{tenant\_id}/{ticket\_id}/resolve



JSON

{

&#x20; "resolution": "Upstairs room-of-choice delivery is available for £25."

}

Once resolved, future identical questions are answered automatically without escalation.



\--------------------------------------------------------------------------------------------



Roadmap (Production Hardening)

\[ ] Replace flat-file JSON TicketStore with PostgreSQL + SQLAlchemy



\[ ] Add JWT / API Key authentication for tenant management and ticket resolution endpoints



\[ ] Enforce per-tenant domain CORS whitelisting for widget security



\[ ] Move web scraping to asynchronous background workers (Redis + Celery/ARQ)



\[ ] Build a React/Next.js merchant dashboard for visual ticket management and token usage analytics









