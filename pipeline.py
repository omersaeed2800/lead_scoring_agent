"""
pipeline.py — The Scoring Engine
Resets all scores to 50 at the start of each run, then rescores based on fresh news.
"""

import os
import json
import time
import requests
import psycopg2
from datetime import datetime, timedelta
from google import genai

# ─── CREDENTIALS (match your .env file exactly) ────────────────────────────────
ACCOUNT_ID       = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
API_TOKEN        = os.environ.get("CLOUDFLARE_API_TOKEN")
NEWS_API_KEY     = os.environ.get("NEWS_API_KEY")
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY")
NEON_CONN_STRING = os.environ.get("NEON_CONNECTION_STRING")


# ─── EMBEDDING ─────────────────────────────────────────────────────────────────

def get_embedding(text: str) -> list:
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/google/embeddinggemma-300m"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        json={"text": [text]}
    )
    data = response.json()
    if data.get("success"):
        return data["result"]["data"][0]
    raise Exception(f"Cloudflare embedding failed: {data.get('errors')}")


# ─── NEWS FETCHING ─────────────────────────────────────────────────────────────

def fetch_news(page_size: int = 100) -> list:
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    params = {
        'q': '(SaaS OR "Series A" OR "Series B" OR "AI Agent" OR "B2B" OR startup OR fintech)',
        'from': start_date,
        'language': 'en',
        'sortBy': 'relevancy',
        'pageSize': page_size,
        'apiKey': NEWS_API_KEY
    }
    response = requests.get("https://newsapi.org/v2/everything", params=params)
    data = response.json()
    articles = data.get("articles", [])
    print(f"[news] fetched {len(articles)} articles")
    return articles


# ─── LLM JUDGE ─────────────────────────────────────────────────────────────────

def get_contextual_score(headline: str, description: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"""
    You are a GTM Strategy Consultant.

    NEWS: {headline}
    COMPANY: {description}

    Evaluate the strategic impact of this news on this company:
    - 50 pts: CRITICAL (Direct match or major market shift for them)
    - 20 pts: RELEVANT (General industry trend)
    - 0 pts:  NOISE (Shared keywords but no actual connection)

    Return ONLY a JSON object: {{"score": int, "reason": "one sentence explanation"}}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt
        )
        clean_json = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_json)
    except Exception as e:
        print(f"[gemini] scoring failed: {e}")
        return {"score": 0, "reason": "Analysis failed"}


# ─── SIGNAL STORAGE ────────────────────────────────────────────────────────────

def store_signal(cur, article: dict, embedding: list) -> int:
    cur.execute("""
        INSERT INTO market_signals (source, raw_text, embedding, sentiment_score, impacted_sectors)
        VALUES (%s, %s, %s::vector, %s, %s)
        RETURNING id;
    """, (
        article.get('source', {}).get('name', 'Unknown'),
        article.get('title', ''),
        embedding,
        0.0,
        []
    ))
    return cur.fetchone()[0]


def log_score_change(cur, lead_id: int, old_score: int, new_score: int,
                     reasoning: str, signal_id: int):
    cur.execute("""
        INSERT INTO score_history (lead_id, old_score, new_score, reasoning, signal_id)
        VALUES (%s, %s, %s, %s, %s);
    """, (lead_id, old_score, new_score, reasoning, signal_id))


# ─── SCORE RESET ───────────────────────────────────────────────────────────────

def reset_all_scores(cur):
    """Resets every lead back to 50 at the start of each pipeline run."""
    cur.execute("UPDATE leads SET current_score = 50, last_scored_at = NULL;")
    print("[reset] all scores reset to 50")


# ─── MAIN PIPELINE ─────────────────────────────────────────────────────────────

def run_pipeline():
    conn = psycopg2.connect(NEON_CONN_STRING)
    cur = conn.cursor()

    # Step 0: Reset all scores before rescoring
    reset_all_scores(cur)
    conn.commit()

    articles = fetch_news(page_size=100)
    print(f"\n[pipeline] starting — {len(articles)} signals to process")
    print("-" * 60)

    matched = 0

    for i, article in enumerate(articles):
        headline = article.get('title', '')
        if not headline:
            continue

        try:
            # Stage 1: embed the headline
            news_vector = get_embedding(headline)

            # Stage 2: store the signal
            signal_id = store_signal(cur, article, news_vector)
            conn.commit()

            # Stage 3: vector search
            cur.execute("""
                SELECT id, company_name, description, current_score
                FROM leads
                WHERE 1 - (embedding <=> %s::vector) > 0.55
                ORDER BY 1 - (embedding <=> %s::vector) DESC
                LIMIT 1;
            """, (news_vector, news_vector))
            match = cur.fetchone()

            if match:
                lead_id, name, desc, old_score = match

                # Stage 4: LLM judge
                analysis = get_contextual_score(headline, desc)
                impact = analysis['score']

                if impact > 0:
                    new_score = old_score + impact

                    cur.execute("""
                        UPDATE leads
                        SET current_score = %s, last_scored_at = NOW()
                        WHERE id = %s;
                    """, (new_score, lead_id))

                    log_score_change(cur, lead_id, old_score, new_score,
                                     analysis['reason'], signal_id)
                    conn.commit()

                    matched += 1
                    print(f"[{i+1}/{len(articles)}] MATCH: {name}")
                    print(f"  NEWS:   {headline[:65]}...")
                    print(f"  SCORE:  {old_score} → {new_score} (+{impact})")
                    print(f"  WHY:    {analysis['reason']}")
                    print("-" * 40)

            time.sleep(0.3)

        except Exception as e:
            print(f"[{i+1}] failed: {headline[:50]}... | {e}")
            continue

    cur.close()
    conn.close()
    print(f"\n[pipeline] done — {matched} leads updated out of {len(articles)} signals")


# ─── ENTRYPOINT ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_pipeline()
