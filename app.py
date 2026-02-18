"""
app.py — YC Startup Intelligence Dashboard
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from db import (
    fetch_top_leads,
    fetch_recent_signals,
    fetch_score_history,
    fetch_score_over_time,
    fetch_dashboard_stats
)

# ─── PAGE CONFIG ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="YC Intelligence Engine",
    page_icon="🚀",
    layout="wide"
)

# ─── HEADER ────────────────────────────────────────────────────────────────────

st.title("🚀 YC Startup Intelligence Engine")
st.caption("Real-time market signal scoring for YC F24 companies")

# ─── STATS ROW ─────────────────────────────────────────────────────────────────

try:
    stats = fetch_dashboard_stats()
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Leads", stats["total_leads"])
    col2.metric("Market Signals Processed", stats["total_signals"])
    col3.metric("Score Updates (24h)", stats["updates_today"])
    if stats["top_company"]:
        col4.metric("🔥 Top Company", stats["top_company"][0],
                    f"Score: {stats['top_company'][1]}")
except Exception as e:
    st.error(f"Could not load stats: {e}")

st.divider()

# ─── MAIN LAYOUT ───────────────────────────────────────────────────────────────

left, right = st.columns([2, 1])

# ── LEFT: Leaderboard ──────────────────────────────────────────────────────────

with left:
    st.subheader("📊 Lead Leaderboard")

    try:
        leads = fetch_top_leads(limit=50)
        if leads:
            df = pd.DataFrame(leads, columns=[
                "ID", "Company", "Description", "Score", "Last Scored", "Status"
            ])

            # Color-code status
            def status_badge(status):
                colors = {
                    "new": "🔵",
                    "contacted": "🟢",
                    "disqualified": "🔴"
                }
                return f"{colors.get(status, '⚪')} {status}"

            df["Status"] = df["Status"].apply(status_badge)
            df["Last Scored"] = pd.to_datetime(df["Last Scored"]).dt.strftime("%b %d, %H:%M")
            df["Description"] = df["Description"].str[:80] + "..."

            st.dataframe(
                df[["Company", "Score", "Status", "Last Scored", "Description"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score",
                        min_value=0,
                        max_value=500,
                    )
                }
            )
        else:
            st.info("No leads found. Run the pipeline first.")
    except Exception as e:
        st.error(f"Could not load leaderboard: {e}")

# ── RIGHT: Recent Signals ──────────────────────────────────────────────────────

with right:
    st.subheader("📡 Recent Market Signals")

    try:
        signals = fetch_recent_signals(limit=15)
        if signals:
            for source, raw_text, sentiment, sectors, created_at in signals:
                with st.container():
                    timestamp = pd.to_datetime(created_at).strftime("%b %d, %H:%M")
                    sentiment_icon = "📈" if sentiment > 0 else ("📉" if sentiment < 0 else "➖")
                    st.markdown(f"**{sentiment_icon} {source}** · {timestamp}")
                    st.caption(raw_text[:120] + "..." if len(raw_text) > 120 else raw_text)
                    st.divider()
        else:
            st.info("No signals yet.")
    except Exception as e:
        st.error(f"Could not load signals: {e}")

# ─── COMPANY DEEP DIVE ─────────────────────────────────────────────────────────

st.divider()
st.subheader("🔍 Company Deep Dive")

try:
    leads_for_select = fetch_top_leads(limit=50)
    if leads_for_select:
        company_options = {row[1]: row[0] for row in leads_for_select}  # name → id
        selected_company = st.selectbox("Select a company", list(company_options.keys()))

        if selected_company:
            lead_id = company_options[selected_company]

            tab1, tab2 = st.tabs(["📈 Score Over Time", "📋 Score History"])

            with tab1:
                timeline = fetch_score_over_time(lead_id)
                if timeline:
                    timeline_df = pd.DataFrame(timeline, columns=["Date", "Score"])
                    timeline_df["Date"] = pd.to_datetime(timeline_df["Date"])
                    st.line_chart(timeline_df.set_index("Date")["Score"])
                else:
                    st.info("No score history yet for this company.")

            with tab2:
                history = fetch_score_history(lead_id)
                if history:
                    history_df = pd.DataFrame(history, columns=[
                        "Old Score", "New Score", "Reasoning", "Date", "Signal"
                    ])
                    history_df["Date"] = pd.to_datetime(history_df["Date"]).dt.strftime("%b %d, %H:%M")
                    history_df["Delta"] = history_df["New Score"] - history_df["Old Score"]
                    history_df["Signal"] = history_df["Signal"].str[:80] + "..."
                    st.dataframe(
                        history_df[["Date", "Old Score", "New Score", "Delta", "Reasoning", "Signal"]],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No history yet.")
except Exception as e:
    st.error(f"Deep dive failed: {e}")

# ─── AUTO REFRESH ──────────────────────────────────────────────────────────────

st.divider()
col_refresh, col_note = st.columns([1, 3])
with col_refresh:
    if st.button("🔄 Refresh Data"):
        st.rerun()
with col_note:
    st.caption("Dashboard reads from Neon Postgres. Scores update when the pipeline runs.")
