"""
VARYNT – AI Lead Qualification + Smart Response System
Backend: FastAPI + Anthropic Claude
"""

import os
import json
import time
import logging
import asyncio
from datetime import datetime
from typing import Optional
from uuid import uuid4

from groq import Groq
import groq as groq_module
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("varynt")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="VARYNT Lead Qualification API",
    description="AI-powered lead classification and personalised response system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Anthropic client ──────────────────────────────────────────────────────────
client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

# ── In-memory store (replace with PostgreSQL / Redis in production) ───────────
leads_db: dict[str, dict] = {}

# ── Pydantic models ───────────────────────────────────────────────────────────
class LeadInput(BaseModel):
    name: str
    email: str
    company: Optional[str] = ""
    role: Optional[str] = ""
    message: str
    budget: Optional[str] = ""
    timeline: Optional[str] = ""
    source: Optional[str] = "web-form"

    @validator("message")
    def message_not_empty(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError("Message is too short to qualify.")
        return v.strip()


class LeadResponse(BaseModel):
    lead_id: str
    classification: str          # Hot / Warm / Cold
    confidence: float            # 0.0 – 1.0
    score: int                   # 0-100
    reasoning: str
    personalised_reply: str
    next_action: str
    processed_at: str


# ── Prompts ───────────────────────────────────────────────────────────────────

CLASSIFICATION_SYSTEM = """You are a senior B2B sales intelligence engine for VARYNT, 
an AI-powered media and marketing platform. Your job is to classify inbound leads 
with surgical precision.

Classification tiers:
- HOT  → Clear intent to buy, specific budget, short timeline (<30 days), decision-maker
- WARM → Interested but vague on budget/timeline, researcher or influencer role
- COLD → Exploratory, no budget, student, spam, or irrelevant inquiry

Return ONLY valid JSON — no markdown, no prose — matching this schema exactly:
{
  "classification": "Hot" | "Warm" | "Cold",
  "confidence": <float 0.0-1.0>,
  "score": <int 0-100>,
  "reasoning": "<1-2 sentence justification>",
  "next_action": "<specific CRM action to take>"
}

Scoring rubric (add points):
+30  explicit budget mentioned
+20  decision-maker title (CEO, CMO, Founder, VP, Director)
+15  timeline under 30 days
+15  specific product/feature request
+10  company name provided
+10  clear pain point articulated
-20  student / learning only
-30  competitor research
-40  spam indicators or nonsensical text"""


def build_classification_prompt(lead: LeadInput) -> str:
    return f"""Classify this inbound lead for VARYNT:

Name: {lead.name}
Email: {lead.email}
Company: {lead.company or "Not provided"}
Role: {lead.role or "Not provided"}
Budget: {lead.budget or "Not mentioned"}
Timeline: {lead.timeline or "Not mentioned"}
Source: {lead.source}
Message:
\"\"\"
{lead.message}
\"\"\"

Apply the scoring rubric strictly. Return JSON only."""


RESPONSE_SYSTEM = """You are VARYNT's AI account executive — sharp, consultative, 
and deeply human. Write personalised outbound replies to inbound leads.

Rules for great replies:
1. Open with a specific hook tied to THEIR message (never generic "Thanks for reaching out")
2. Mirror their vocabulary and energy level
3. For Hot leads: move fast — propose a call with 2 specific time slots
4. For Warm leads: provide value first (insight, resource, question) before asking for call
5. For Cold leads: be helpful and brief, no hard sell
6. Keep replies under 180 words
7. NEVER hallucinate features VARYNT doesn't have — stick to: AI content creation, 
   lead qualification, smart response automation, analytics dashboards, CRM integrations
8. End with ONE clear CTA only
9. Sign off as: Alex Chen, Growth @ VARYNT"""


def build_response_prompt(lead: LeadInput, classification: str, reasoning: str) -> str:
    return f"""Write a personalised reply for this {classification} lead:

Lead context:
- Name: {lead.name}
- Company: {lead.company or "unknown company"}
- Role: {lead.role or "unknown role"}
- Their message: "{lead.message}"
- Budget signal: {lead.budget or "none"}
- Timeline: {lead.timeline or "unspecified"}
- Why classified {classification}: {reasoning}

Write the email reply body only (no subject line, no JSON wrapper)."""


# ── Core AI pipeline ──────────────────────────────────────────────────────────

async def classify_lead(lead: LeadInput, retries: int = 2) -> dict:
    """Call Groq to classify the lead. Retries on failure."""
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=400,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM},
                    {"role": "user", "content": build_classification_prompt(lead)},
                ],
            )
            raw = response.choices[0].message.content.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)

            assert result["classification"] in ("Hot", "Warm", "Cold")
            assert 0 <= result["confidence"] <= 1
            assert 0 <= result["score"] <= 100
            return result

        except (json.JSONDecodeError, KeyError, AssertionError) as e:
            logger.warning(f"Classification parse error (attempt {attempt+1}): {e}")
            if attempt == retries:
                return {
                    "classification": "Warm",
                    "confidence": 0.4,
                    "score": 40,
                    "reasoning": "Fallback classification due to parsing error.",
                    "next_action": "Manual review required",
                }
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Groq API error during classification: {e}")
            if attempt == retries:
                return {
                    "classification": "Warm",
                    "confidence": 0.3,
                    "score": 30,
                    "reasoning": "API error — assigned Warm pending manual review.",
                    "next_action": "Queue for manual review",
                }
            await asyncio.sleep(1)


async def generate_response(lead: LeadInput, classification: str, reasoning: str) -> str:
    """Generate personalised reply using Groq."""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=400,
            messages=[
                {"role": "system", "content": RESPONSE_SYSTEM},
                {
                    "role": "user",
                    "content": build_response_prompt(lead, classification, reasoning),
                },
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        return (
            f"Hi {lead.name},\n\nThank you for reaching out to VARYNT. "
            "Our team will be in touch within 24 hours.\n\nBest,\nAlex Chen, Growth @ VARYNT"
        )


def validate_lead_quality(lead: LeadInput) -> Optional[str]:
    """Detect garbage/spam input before hitting the LLM."""
    msg = lead.message.strip()

    if len(msg) < 10:
        return "Message too short"
    if len(set(msg)) < 5:
        return "Repetitive/garbage input detected"
    spam_patterns = ["test123", "asdfgh", "qwerty", "xxxxxxx", "hello world"]
    if any(p in msg.lower() for p in spam_patterns):
        return "Likely test/spam submission"
    if not any(c.isalpha() for c in msg):
        return "No readable text in message"

    return None  # Passed


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/qualify-lead", response_model=LeadResponse)
async def qualify_lead(lead: LeadInput, background_tasks: BackgroundTasks):
    lead_id = str(uuid4())
    start = time.time()

    logger.info(f"[{lead_id}] New lead: {lead.email} | source={lead.source}")

    # ── 1. Input validation / garbage check ──────────────────────────────────
    quality_issue = validate_lead_quality(lead)
    if quality_issue:
        logger.warning(f"[{lead_id}] Low-quality input: {quality_issue}")
        # Still store it, but flag as Cold automatically
        classification_data = {
            "classification": "Cold",
            "confidence": 0.9,
            "score": 5,
            "reasoning": f"Auto-rejected: {quality_issue}",
            "next_action": "Archive — do not contact",
        }
        reply = (
            f"Hi {lead.name}, thanks for getting in touch. "
            "We'll review your message and reach out if there's a fit. — VARYNT Team"
        )
    else:
        # ── 2. Parallel LLM calls ─────────────────────────────────────────────
        classification_data = await classify_lead(lead)
        reply = await generate_response(
            lead,
            classification_data["classification"],
            classification_data["reasoning"],
        )

    elapsed = round(time.time() - start, 2)
    logger.info(
        f"[{lead_id}] Classified={classification_data['classification']} "
        f"score={classification_data['score']} elapsed={elapsed}s"
    )

    # ── 3. Persist (background task so it doesn't block response) ────────────
    record = {
        "lead_id": lead_id,
        "lead": lead.dict(),
        "classification": classification_data["classification"],
        "confidence": classification_data["confidence"],
        "score": classification_data["score"],
        "reasoning": classification_data["reasoning"],
        "next_action": classification_data["next_action"],
        "personalised_reply": reply,
        "processed_at": datetime.utcnow().isoformat(),
        "elapsed_seconds": elapsed,
    }
    background_tasks.add_task(save_lead, lead_id, record)

    return LeadResponse(
        lead_id=lead_id,
        classification=classification_data["classification"],
        confidence=classification_data["confidence"],
        score=classification_data["score"],
        reasoning=classification_data["reasoning"],
        personalised_reply=reply,
        next_action=classification_data["next_action"],
        processed_at=record["processed_at"],
    )


@app.get("/api/leads")
def list_leads():
    """Return all stored leads (replace with real DB query in production)."""
    return {
        "count": len(leads_db),
        "leads": list(leads_db.values()),
    }


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: str):
    if lead_id not in leads_db:
        raise HTTPException(status_code=404, detail="Lead not found")
    return leads_db[lead_id]


# ── Background helpers ────────────────────────────────────────────────────────

def save_lead(lead_id: str, record: dict):
    """Persist lead to in-memory store. Swap for DB write in production."""
    leads_db[lead_id] = record
    logger.info(f"[{lead_id}] Saved to store")