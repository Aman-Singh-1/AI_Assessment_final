# VARYNT – AI Lead Qualification + Smart Response System

> **Final Assessment Submission** 



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

Just open index.html` in any browser. 


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
sment | Dream Reflection Media*
