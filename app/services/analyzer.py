import json
import re
from fastapi import HTTPException
from anthropic import Anthropic
from app.config import settings
from pydantic import BaseModel, Field

class KnowledgeGapAnalysis(BaseModel):
    summary_of_findings: str = Field(..., description="Brief summary of what was successfully scraped.")
    identified_gaps: list[str] = Field(..., description="Missing policy areas, vague info, or unclear timelines found.")
    follow_up_questions: list[str] = Field(
        ..., 
        min_length=5, 
        max_length=8, 
        description="Targeted questions for the owner to fill knowledge gaps."
    )

class GapAnalyzerService:
    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def analyze_scraped_content(self, business_name: str, scraped_pages: dict[str, str]) -> KnowledgeGapAnalysis:
        combined_text = ""
        for page_name, content in scraped_pages.items():
            combined_text += f"\n\n--- PAGE: {page_name.upper()} ---\n{content[:4000]}"

        prompt = f"""
        You are an expert customer support knowledge engineer auditing a business named '{business_name}'.
        Analyze the scraped website content below. Identify missing customer support policies (e.g., return windows, shipping tiers, international handling, refund methods, or operating hours).
        
        Generate 5 to 8 precise, targeted follow-up questions that the business owner must answer to plug these knowledge gaps so a RAG customer service chatbot can answer accurately.
        
        Scraped Website Content:
        {combined_text[:15000]}
        
        You must reply ONLY in valid JSON matching this exact schema:
        {{
          "summary_of_findings": "string",
          "identified_gaps": ["string"],
          "follow_up_questions": ["string"]
        }}
        """

        try:
            response = self.client.messages.create(
                model="claude-sonnet-5-5",
                max_tokens=4096,
                system="You are an automated knowledge auditor. Output strictly valid JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Anthropic API Error: {str(e)}")

        raw_text = response.content[0].text.strip()
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            raise HTTPException(status_code=500, detail=f"Failed to parse JSON from LLM output: {raw_text[:200]}")

        parsed_data = json.loads(match.group(0))
        return KnowledgeGapAnalysis(**parsed_data)