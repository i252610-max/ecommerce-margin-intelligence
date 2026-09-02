import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------- Configuration ----------
DB_PATH = Path(__file__).resolve().parents[2] / "database" / "competitor_data.db"

# ---------- Cached Data Loader ----------
@st.cache_data(ttl=60)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load five tables from SQLite:
    - product_profitability
    - customer_risk_scores
    - margin_breach_alerts (active)
    - internal_orders
    - internal_customers
    """
    conn = sqlite3.connect(DB_PATH)

    profitability = pd.read_sql_query("SELECT * FROM product_profitability", conn)
    risk = pd.read_sql_query("SELECT * FROM customer_risk_scores", conn)
    alerts = pd.read_sql_query("SELECT * FROM margin_breach_alerts WHERE status != 'rejected'", conn)
    orders = pd.read_sql_query("SELECT * FROM internal_orders", conn)
    customers = pd.read_sql_query("SELECT customer_id, region FROM internal_customers", conn)

    conn.close()
    return profitability, risk, alerts, orders, customers

# ---------- Page Config ----------
st.set_page_config(page_title="Executive Command Center", layout="wide")
st.title("📊 Executive Command Center")
st.caption("Live operational intelligence from the margin & churn pipeline")

# ---------- RLS Region Selector ----------
regions = ["National", "North", "South", "East", "West"]
selected_region = st.selectbox("View Data As:", regions, key="region_selector")
st.session_state['current_region'] = selected_region

# ---------- Load all data ----------
profitability_df, risk_df, alerts_df, orders_df, customers_df = load_data()

# ---------- Apply RLS filter to risk data ----------
if selected_region != "National":
    risk_df = risk_df[risk_df['region'] == selected_region]

# ---------- Compute region-filtered revenue ----------
# Revenue is order-grain (region-filterable); profitability chart is product-grain (national by design).
if selected_region != "National":
    region_customer_ids = customers_df[customers_df['region'] == selected_region]['customer_id']
    region_orders = orders_df[orders_df['customer_id'].isin(region_customer_ids)]
    total_revenue = (region_orders['quantity'] * region_orders['unit_price']).sum()
else:
    total_revenue = (orders_df['quantity'] * orders_df['unit_price']).sum()

# ---------- Compute overall margin ----------
# Using product_profitability (national) for margin, as it's product-level aggregation.
total_profit_national = profitability_df['total_profit'].sum()
overall_margin = (total_profit_national / profitability_df['total_revenue'].sum() * 100) if profitability_df['total_revenue'].sum() else 0

# ---------- KPI Row ----------
bleeding_products = (profitability_df['total_profit'] < 0).sum()
high_risk_customers = (risk_df['risk_flag'] == 'HIGH').sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Revenue", f"${total_revenue:,.0f}")
c2.metric("Overall Margin", f"{overall_margin:.1f}%")
c3.metric("Bleeding Products", bleeding_products, delta_color="inverse")
c4.metric("High-Risk Customers", high_risk_customers)

st.caption(f"🔒 Viewing restricted data for: {selected_region} Region")

st.divider()

# ---------- Profitability Diverging Bar Chart (product-grain, national) ----------
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
    title="Top 10 & Bottom 10 Products by Profit (National)",
)
fig_bar.update_layout(
    yaxis={"categoryorder": "total ascending"},
    showlegend=False,
    height=600,
)

# ---------- Churn Risk Donut Chart (region-filtered) ----------
risk_counts = risk_df["risk_flag"].value_counts().reset_index()
risk_counts.columns = ["risk_flag", "count"]

fig_donut = px.pie(
    risk_counts,
    values="count",
    names="risk_flag",
    hole=0.4,
    color="risk_flag",
    color_discrete_map={"HIGH": "#d62728", "MEDIUM": "#ff7f0e", "LOW": "#2ca02c"},
    title=f"Customer Churn Risk Distribution ({selected_region})",
)

# ---------- Side-by-side layout ----------
left, right = st.columns([2, 1])
with left:
    st.plotly_chart(fig_bar, width="stretch")
with right:
    st.plotly_chart(fig_donut, width="stretch")

# ---------- Footer ----------
st.markdown("---")
st.info("Data refreshed live from SQLite via the master pipeline.")