import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------- Configuration ----------
DB_PATH = Path(__file__).resolve().parents[2] / "database" / "competitor_data.db"

# ---------- Database writer ----------
def update_match_status(match_id: int, new_status: str):
    """
    Update the status of a specific match row in product_matches.
    new_status: 'manual' for confirm, 'rejected' for reject.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE product_matches
        SET status = ?
        WHERE id = ?
    """, (new_status, match_id))
    conn.commit()
    conn.close()

# ---------- Cached Data Fetcher ----------
@st.cache_data(ttl=60)
def fetch_review_queue() -> pd.DataFrame:
    """Fetch needs_review matches joined with internal product details."""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            pm.id,
            pm.internal_product_id,
            pm.competitor,
            pm.competitor_product_name,
            pm.match_score,
            pm.status,
            ip.product_name AS internal_product_name,
            ip.category AS internal_category,
            ip.cost AS internal_cost
        FROM product_matches pm
        LEFT JOIN internal_products ip
            ON pm.internal_product_id = ip.product_id
        WHERE pm.status = 'needs_review'
        ORDER BY pm.match_score DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ---------- Page Config ----------
st.set_page_config(page_title="Match Review Queue", layout="wide")
st.title("🧠 Match Review Queue")
st.caption("Human-in-the-loop: confirm or reject ambiguous fuzzy matches")

# ---------- Load data ----------
df_review = fetch_review_queue()

# ---------- Metric ----------
st.metric("Pairs Awaiting Judgment", len(df_review))

# ---------- Main UI (only if there are items) ----------
if len(df_review) > 0:
    for idx, row in df_review.iterrows():
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown(f"**{row['internal_product_name']}**")
            st.caption(f"ID: {row['internal_product_id']} | Category: {row['internal_category']} | Cost: ${row['internal_cost']:.2f}")

        with col_right:
            st.markdown(f"**{row['competitor_product_name']}**")
            st.caption(f"Competitor: {row['competitor']} | Score: {row['match_score']:.1f}")

        col_btn1, col_btn2, _ = st.columns([0.2, 0.2, 0.6])
        with col_btn1:
            confirm_clicked = st.button("✅ Confirm", key=f"confirm_{row['id']}")
        with col_btn2:
            reject_clicked = st.button("❌ Reject", key=f"reject_{row['id']}")

        # Handle button actions
        if confirm_clicked:
            update_match_status(row["id"], "manual")
            st.toast("✅ Match confirmed and saved!", icon="🎉")
            st.cache_data.clear()   # ensure fresh data on rerun
            st.rerun()

        if reject_clicked:
            update_match_status(row["id"], "rejected")
            st.toast("❌ Match rejected.", icon="🚫")
            st.cache_data.clear()
            st.rerun()

        st.divider()
else:
    st.success("🎉 Queue Cleared! All pairs have been reviewed.")
    st.balloons()

# ---------- Footer ----------
st.markdown("---")
st.info("Decisions are saved instantly to the database.")