import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- Configuration ----------
DB_PATH = Path(__file__).resolve().parent.parent / "database" / "competitor_data.db"

# ---------- Cached Data Loader ----------
@st.cache_data(ttl=60)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load three analytical tables from SQLite into DataFrames.
    Returns (profitability_df, risk_df, alerts_df).
    """
    conn = sqlite3.connect(DB_PATH)

    profitability = pd.read_sql_query("SELECT * FROM product_profitability", conn)
    risk = pd.read_sql_query("SELECT * FROM customer_risk_scores", conn)
    alerts = pd.read_sql_query("SELECT * FROM margin_breach_alerts WHERE status != 'rejected'", conn)

    conn.close()
    return profitability, risk, alerts

# ---------- Load data ----------
profitability_df, risk_df, alerts_df = load_data()

# ---------- Page Config ----------
st.set_page_config(page_title="Executive Command Center", layout="wide")
st.title("📊 Executive Command Center")
st.caption("Live operational intelligence from the margin & churn pipeline")

# ---------- KPI Row ----------
total_revenue = profitability_df["total_revenue"].sum()
overall_margin = (profitability_df["total_profit"].sum() / total_revenue * 100) if total_revenue else 0
bleeding_products = (profitability_df["total_profit"] < 0).sum()
high_risk_customers = (risk_df["risk_flag"] == "HIGH").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"${total_revenue:,.0f}")
c2.metric("Overall Margin", f"{overall_margin:.1f}%")
c3.metric("Bleeding Products", bleeding_products, delta_color="inverse")
c4.metric("High-Risk Customers", high_risk_customers)

st.divider()

# ---------- Profitability Diverging Bar Chart ----------
# Take top 10 and bottom 10 by total_profit for clarity
top10 = profitability_df.nlargest(10, "total_profit")
bottom10 = profitability_df.nsmallest(10, "total_profit")
plot_df = pd.concat([top10, bottom10]).drop_duplicates()
plot_df["is_profitable"] = plot_df["total_profit"] > 0

fig_bar = px.bar(
    plot_df,
    x="total_profit",
    y="product_name",
    orientation="h",
    color="is_profitable",
    color_discrete_map={True: "#2ca02c", False: "#d62728"},
    labels={"total_profit": "Total Profit ($)", "product_name": "Product"},
    title="Top 10 & Bottom 10 Products by Profit",
)
fig_bar.update_layout(
    yaxis={"categoryorder": "total ascending"},  # winners on top, losers bottom
    showlegend=False,
    height=600,
)

# ---------- Churn Risk Donut Chart ----------
risk_counts = risk_df["risk_flag"].value_counts().reset_index()
risk_counts.columns = ["risk_flag", "count"]

fig_donut = px.pie(
    risk_counts,
    values="count",
    names="risk_flag",
    hole=0.4,
    color="risk_flag",
    color_discrete_map={"HIGH": "#d62728", "MEDIUM": "#ff7f0e", "LOW": "#2ca02c"},
    title="Customer Churn Risk Distribution",
)

# ---------- Side-by-side layout ----------
left, right = st.columns([2, 1])
with left:
    st.plotly_chart(fig_bar, use_container_width=True)
with right:
    st.plotly_chart(fig_donut, use_container_width=True)

# ---------- Footer ----------
st.markdown("---")
st.info("Data refreshed live from SQLite via the master pipeline.")