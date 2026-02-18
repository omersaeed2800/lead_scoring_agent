import psycopg2
import streamlit as st


def get_connection():
    import os
    conn_string = os.environ.get("NEON_CONNECTION_STRING") or st.secrets.get("NEON_CONNECTION_STRING")
    return psycopg2.connect(conn_string)


Save the file, then in your terminal:
```
cd C:\Apps\YC_GTM
git add .
git commit -m "fix db connection"
git push origin master


def fetch_top_leads(limit=50):
    """Fetch top leads ranked by current_score."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, company_name, description, current_score, last_scored_at, status
        FROM leads
        ORDER BY current_score DESC
        LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_recent_signals(limit=20):
    """Fetch the most recent market signals."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT source, raw_text, sentiment_score, impacted_sectors, created_at
        FROM market_signals
        ORDER BY created_at DESC
        LIMIT %s;
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_score_history(lead_id):
    """Fetch full score history for a specific company."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT sh.old_score, sh.new_score, sh.reasoning, sh.created_at,
               ms.raw_text as signal_text
        FROM score_history sh
        LEFT JOIN market_signals ms ON sh.signal_id = ms.id
        WHERE sh.lead_id = %s
        ORDER BY sh.created_at DESC;
    """, (lead_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_score_over_time(lead_id):
    """Fetch score timeline for charting."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT created_at, new_score
        FROM score_history
        WHERE lead_id = %s
        ORDER BY created_at ASC;
    """, (lead_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_dashboard_stats():
    """Quick summary stats for the top of the dashboard."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM leads;")
    total_leads = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM market_signals;")
    total_signals = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM score_history WHERE created_at > NOW() - INTERVAL '24 hours';")
    updates_today = cur.fetchone()[0]

    cur.execute("SELECT company_name, current_score FROM leads ORDER BY current_score DESC LIMIT 1;")
    top_company = cur.fetchone()

    cur.close()
    conn.close()
    return {
        "total_leads": total_leads,
        "total_signals": total_signals,
        "updates_today": updates_today,
        "top_company": top_company
    }
