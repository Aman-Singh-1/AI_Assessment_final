# VARYNT – AI Lead Qualification + Smart Response System

> **Final Assessment Submission** 



### Step-by-Step Setup

#### 1 — Clone / copy the project

```bash
# If you have git
git clone https://github.com/Aman-Singh-1/AI_Assessment_final
cd AI_Assessment_final

# Or just copy the folder structure shown below
```

#### 2 — Set up the backend

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Add your GROQ API key
cp .env.example .env
# Open .env and set:  Groq_API_Key=sk-ant-xxxxxxxxxxxx
```

#### 3 — Run the backend


uvicorn main:app --reload --port 8000

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8001
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
GET  http://localhost:8001/health          — health check
POST http://localhost:8001/api/qualify-lead — classify a lead
GET  http://localhost:8001/api/leads       — list all stored leads
GET  http://localhost:8001/docs            — Swagger UI
```

Example cURL:

```bash
curl -X POST http://localhost:8001/api/qualify-lead \
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
