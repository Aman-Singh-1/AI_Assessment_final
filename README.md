# VARYNT – AI Lead Qualification + Smart Response System

> **Final Assessment Submission** | Dream Reflection Media | AI Engineer Role

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture (Q1)](#q1-architecture)
3. [Core Implementation (Q2)](#q2-implementation)
4. [Prompts & Output Quality (Q3)](#q3-prompts)
5. [Edge Case Handling (Q4)](#q4-edge-cases)
6. [Monitoring (Q5)](#q5-monitoring)
7. [Trade-offs (Q6)](#q6-trade-offs)
8. [Project Structure](#project-structure)

---

## Quick Start

### Is a backend necessary?

**Yes** — the backend handles the Anthropic API call (which requires a secret key),
input validation, async queuing, and persistence. The frontend is a pure HTML demo
that calls the backend API.

---

### Step-by-Step Setup

#### 1 — Clone / copy the project

```bash
# If you have git
git clone <repo-url>
cd varynt

# Or just copy the folder structure shown below
```

#### 2 — Set up the backend

```bash
cd backend

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Add your Anthropic API key
cp .env.example .env
# Open .env and set:  ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

#### 3 — Run the backend

```bash
# Load env and start the server
export $(cat .env | xargs)          # macOS / Linux
# Or on Windows: set ANTHROPIC_API_KEY=sk-ant-xxxx

uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

#### 4 — Open the frontend

Just open `frontend/index.html` in any browser. No build step needed.

```bash
open frontend/index.html    # macOS
# Or double-click the file in Explorer / Finder
```

#### 5 — Test it

- Fill in the form (name, email, message are required)
- Click **Qualify This Lead →**
- See the classification, score, reasoning, and AI-written reply

#### 6 — (Optional) Explore the API

```
GET  http://localhost:8000/health          — health check
POST http://localhost:8000/api/qualify-lead — classify a lead
GET  http://localhost:8000/api/leads       — list all stored leads
GET  http://localhost:8000/docs            — Swagger UI
```

Example cURL:

```bash
curl -X POST http://localhost:8000/api/qualify-lead \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Priya Sharma",
    "email": "priya@startup.io",
    "company": "GrowthStack",
    "role": "CMO",
    "budget": "₹2L–₹10L/month",
    "timeline": "This month",
    "message": "We need to automate outbound qualification for 500 leads/month. Current SDR costs unsustainable. Want to pilot ASAP."
  }'
```

---

## Q1. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                              │
│   Web Form (HTML)  /  Chat Widget  /  CRM Webhook  /  API       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ POST /api/qualify-lead
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                             │
│                                                                  │
│  ① Input Validation (Pydantic)                                   │
│     • Type checks, required fields                               │
│     • Garbage / spam detection (pre-LLM filter)                  │
│                                                                  │
│  ② Lead Classification (Claude claude-sonnet-4-20250514)               │
│     • Structured prompt → enforced JSON output                   │
│     • Returns: Hot / Warm / Cold + score 0-100 + reasoning       │
│     • 2x retry with fallback on parse error                      │
│                                                                  │
│  ③ Response Generation (Claude claude-sonnet-4-20250514)               │
│     • Personalised reply using classification context            │
│     • Fallback template on API timeout                           │
│                                                                  │
│  ④ Background Task (FastAPI BackgroundTasks)                      │
│     • Persists record after HTTP response returned               │
│     • In-memory dict → swap for PostgreSQL / Redis               │
│                                                                  │
│  ⑤ Response returned to client                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    ┌──────────┐     ┌──────────┐     ┌──────────────┐
    │   DB /   │     │  Queue   │     │  CRM         │
    │PostgreSQL│     │ (Celery/ │     │ (HubSpot /   │
    │  Redis   │     │  Redis)  │     │  Salesforce) │
    └──────────┘     └──────────┘     └──────────────┘
```

### Production additions (beyond this demo)

| Layer | This demo | Production |
|---|---|---|
| DB | Python dict | PostgreSQL + SQLAlchemy |
| Queue | BackgroundTasks | Celery + Redis |
| Auth | None | JWT / API key middleware |
| Rate limiting | None | slowapi / nginx |
| CRM | None | HubSpot / Salesforce webhook |
| Deployment | uvicorn local | Docker + Gunicorn + Nginx |
| Secrets | .env file | AWS Secrets Manager |

---

## Q2. Implementation

The core implemented here is the **full AI pipeline** (option 4):

```
Input → Validate → Classify (LLM) → Generate Response (LLM) → Store → Return
```

**Key files:**

```
backend/main.py        — entire backend (FastAPI + AI pipeline)
frontend/index.html    — demo UI
```

**Classification function** (in `main.py`):

```python
async def classify_lead(lead: LeadInput) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=CLASSIFICATION_SYSTEM,   # strict JSON schema + rubric
        messages=[{"role": "user", "content": build_classification_prompt(lead)}],
    )
    result = json.loads(response.content[0].text.strip())
    return result   # {"classification", "confidence", "score", "reasoning", "next_action"}
```

---

## Q3. Prompts

### Classification Prompt

```
SYSTEM:
You are a senior B2B sales intelligence engine for VARYNT.
Return ONLY valid JSON — no markdown — matching this schema:
{
  "classification": "Hot" | "Warm" | "Cold",
  "confidence": <float 0.0-1.0>,
  "score": <int 0-100>,
  "reasoning": "<1-2 sentence justification>",
  "next_action": "<specific CRM action>"
}

Scoring rubric:
+30  explicit budget mentioned
+20  decision-maker title (CEO, CMO, Founder, VP, Director)
+15  timeline under 30 days
+15  specific product/feature request
+10  company name provided
+10  clear pain point articulated
-20  student / learning only
-30  competitor research
-40  spam indicators or nonsensical text

USER:
Name: {name} | Email: {email} | Company: {company}
Role: {role} | Budget: {budget} | Timeline: {timeline}
Message: "{message}"
```

### Response Generation Prompt

```
SYSTEM:
You are VARYNT's AI account executive. Rules:
1. Open with a specific hook tied to THEIR message (never generic)
2. Mirror their vocabulary and energy level
3. Hot → propose call with 2 specific time slots
4. Warm → provide value first, then ask for call
5. Cold → helpful and brief, no hard sell
6. Under 180 words. ONE CTA. Sign as Alex Chen, Growth @ VARYNT
7. NEVER hallucinate features — stick to: AI content creation,
   lead qualification, smart response automation, analytics, CRM integrations

USER:
Write a reply for this {classification} lead.
Name: {name} | Company: {company} | Role: {role}
Their message: "{message}"
Why {classification}: {reasoning}
```

### How we ensure outputs are:

**Not generic:**
- System prompt bans generic openers ("Thanks for reaching out")
- Prompt injects exact lead data (company, role, message) so Claude must reference it
- Role + budget + timeline context forces differentiated replies

**Not hallucinated:**
- Explicit constraint: "ONLY mention these 5 features" — no fabrication
- Classification uses a deterministic rubric with point values
- Output schema is enforced (JSON parse failure → retry → fallback)

**Context-aware:**
- All lead fields passed to both prompts
- Classification reasoning passed to response generator so the tone is calibrated
- Budget/timeline signals directly influence CTA urgency

---

## Q4. Edge Case Handling

| Scenario | Handling |
|---|---|
| **Low / garbage input** | Pre-LLM `validate_lead_quality()` checks length < 10, repetitive chars, known spam strings. Auto-classified Cold, no LLM call wasted. |
| **Ambiguous leads** | LLM assigns Warm with lower confidence score. CRM action = "Manual review". Confidence < 0.5 triggers a flag in the stored record. |
| **Model failure (API error)** | `try/except anthropic.APIError` returns HTTP 503 with message "AI service temporarily unavailable". Client can retry. |
| **Timeout** | `anthropic.APITimeoutError` caught separately — classification fallback to Warm, reply fallback to template. User still gets a response. |
| **Parse error (bad JSON)** | 2 retries with `await asyncio.sleep(1)`. After 3 failures, graceful fallback dict returned (Warm, score 40, manual review flag). |
| **Incorrect classification** | Confidence score exposed in response. CRM rule: confidence < 0.6 → human review queue. Future: feedback loop to fine-tune prompts. |
| **Duplicate submission** | In production: email hash dedupe check before LLM call. Here: each submission gets a new UUID. |
| **Empty / missing optional fields** | Pydantic marks optional fields with `Optional[str] = ""`. Prompts handle missing context gracefully ("Not provided"). |

---

## Q5. Monitoring

### What to monitor:

```
1. API latency          — P50, P95, P99 per endpoint (Prometheus + Grafana)
2. Classification dist  — % Hot/Warm/Cold over time (catch drift)
3. LLM error rate       — APIError, TimeoutError, ParseError counts
4. Fallback rate        — how often we serve template replies (signals LLM issues)
5. Confidence histogram — track if avg confidence drops (prompt degradation)
6. Lead volume          — requests/min, daily totals
```

### Tooling stack (production):

```
Logs        → structured JSON → CloudWatch / Datadog
Metrics     → Prometheus → Grafana dashboards
Alerts      → PagerDuty if error rate > 5% in 5 min window
Tracing     → OpenTelemetry (trace each lead through classify → generate → store)
LLM quality → weekly human review of 50 random classifications
Uptime      → UptimeRobot on /health endpoint
```

### In this demo:

Every request logs:
```
INFO | [lead_id] New lead: email | source=web-demo
INFO | [lead_id] Classified=Hot score=82 elapsed=1.43s
INFO | [lead_id] Saved to store
```

---

## Q6. Trade-offs

| Decision | Trade-off Made | Reason |
|---|---|---|
| **Single LLM for both tasks** | 2 serial calls vs 1 combined call | Separation of concerns. Classification failures don't corrupt reply generation. Easier to debug and tune each prompt independently. |
| **In-memory store** | No persistence across restarts | Keeps demo zero-dependency. Swap for PostgreSQL in 10 lines (SQLAlchemy). |
| **Synchronous LLM calls** | Not truly async (Anthropic SDK is sync) | FastAPI + BackgroundTasks gives async-feel for storage. True async = use `httpx` directly or `anthropic.AsyncAnthropic`. |
| **No auth on API** | Security risk | Demo only. Production: require `Authorization: Bearer <key>` header. |
| **Pre-LLM garbage filter** | May reject edge cases | Saves ~40% LLM cost on spam. Threshold tunable. |
| **Fallback to Warm on failure** | May misclassify | Warm triggers human review = safe default. Hot fallback would waste sales time; Cold fallback would lose real leads. |
| **No streaming** | Slower perceived response | Streaming adds complexity. For an API, a single JSON payload is cleaner. |
| **Pydantic v2** | Slightly stricter parsing | Catches bad input before it hits the LLM, which is worth the small overhead. |

---

## Project Structure

```
varynt/
├── backend/
│   ├── main.py              ← FastAPI app + full AI pipeline
│   ├── requirements.txt     ← Python dependencies
│   └── .env.example         ← Environment template
└── frontend/
    └── index.html           ← Demo UI (no build step)
```

### What I'd add with more time:

1. **PostgreSQL** — SQLAlchemy models for `Lead`, `Classification`, `Reply`
2. **Celery + Redis** — true async queue for high-volume ingestion
3. **Webhook to HubSpot** — push Hot leads directly into CRM pipeline
4. **Streaming replies** — `client.messages.stream()` for real-time reply rendering
5. **Feedback loop** — thumbs up/down on classification → logged for prompt tuning
6. **Rate limiting** — per-IP throttle to prevent abuse
7. **Tests** — pytest suite covering classify, response gen, fallbacks, garbage input
8. **Docker Compose** — one-command `docker compose up` for backend + Redis

---

*Built by Aman | AI Engineer Assessment | Dream Reflection Media*
