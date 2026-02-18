# YC Startup Intelligence Engine

Real-time market signal scoring for YC F24 companies using vector search + LLM reasoning.

---

## File Structure

```
yc_intelligence/
├── app.py                    # Streamlit dashboard (READ only — just displays data)
├── db.py                     # All Postgres queries in one place
├── pipeline.py               # Scoring engine (run on a schedule, separate from UI)
├── requirements.txt
├── .env.example              # Template for pipeline credentials
└── .streamlit/
    └── secrets.toml          # Template for Streamlit credentials (local only)
```

---

## Secrets You Need — Full Breakdown

### 1. NEON_CONNECTION_STRING
**What it is:** Your Neon Postgres database URL
**Where to get it:** neon.tech → your project → Connection Details → copy the `postgresql://...` string
**Format:** `postgresql://username:password@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require`
**Used by:** Both `app.py` (via Streamlit secrets) and `pipeline.py` (via env var)

---

### 2. CLOUDFLARE_ACCOUNT_ID
**What it is:** Your Cloudflare account identifier
**Where to get it:** dash.cloudflare.com → right sidebar → "Account ID"
**Format:** 32-character hex string e.g. `a1b2c3d4e5f6...`
**Used by:** `pipeline.py` only (for embedding via Gemma model)

---

### 3. CLOUDFLARE_API_TOKEN
**What it is:** API token with Workers AI permissions
**Where to get it:** dash.cloudflare.com → My Profile → API Tokens → Create Token
**Permissions needed:** `Workers AI — Read` (or use the "Workers AI" template)
**Format:** Long alphanumeric string
**Used by:** `pipeline.py` only

---

### 4. NEWS_API_KEY
**What it is:** Your NewsAPI.org API key
**Where to get it:** newsapi.org → Register → your API key is on the dashboard
**Note:** Free tier allows up to 100 results per request and 100 requests/day.
**Used by:** `pipeline.py` only

---

### 5. GEMINI_API_KEY
**What it is:** Google Gemini API key for the LLM judge
**Where to get it:** aistudio.google.com → Get API Key → Create API key
**Model used:** `gemini-2.0-flash` (fast + cheap, perfect for scoring at scale)
**Used by:** `pipeline.py` only

---

## How to Run Locally

### Dashboard
```bash
pip install -r requirements.txt
# Fill in .streamlit/secrets.toml with your NEON_CONNECTION_STRING
streamlit run app.py
```

### Pipeline (manual trigger)
```bash
cp .env.example .env
# Fill in all values in .env
export $(cat .env | xargs)
python pipeline.py
```

---

## Deployment

### Streamlit Cloud (dashboard)
1. Push to GitHub (make sure `.streamlit/secrets.toml` is in `.gitignore`)
2. Go to share.streamlit.io → New app → connect your repo
3. In "Advanced settings" → Secrets → paste your `NEON_CONNECTION_STRING`

### Pipeline scheduling (options)
- **GitHub Actions** (free): set up a cron workflow that runs `pipeline.py` daily
- **Cloudflare Workers** (fits your stack): cron trigger calling the pipeline logic
- **Railway / Render**: deploy as a background worker with a cron schedule

---

## Architecture

```
NewsAPI (100 articles)
     ↓
Cloudflare Gemma (embed headline)
     ↓
Neon Postgres pgvector (cosine similarity search against leads)
     ↓
Gemini Flash (judge: is this actually relevant?)
     ↓
UPDATE leads.current_score + INSERT score_history
     ↓
Streamlit reads Postgres → Live Dashboard
```
