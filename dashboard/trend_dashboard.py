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
    Load three tables from SQLite:
    - price_history (time series)
    - product_matches (bridge)
    - internal_products (catalog)
    """
    conn = sqlite3.connect(DB_PATH)

    price_history = pd.read_sql_query("SELECT * FROM price_history", conn)
    product_matches = pd.read_sql_query("SELECT * FROM product_matches", conn)
    internal_products = pd.read_sql_query("SELECT * FROM internal_products", conn)

    conn.close()
    return price_history, product_matches, internal_products

# ---------- Load data ----------
price_history_df, matches_df, products_df = load_data()

# ---------- Page Config ----------
st.set_page_config(page_title="Competitor Price Trends", layout="wide")
st.title("📈 Historical Trend Dashboard")
st.caption("Track competitor price movements against your internal cost and price boundaries")

# ---------- Dropdown: only products with valid matches ----------
# Filter matches to only 'auto' or 'manual' statuses
valid_matches = matches_df[matches_df["status"].isin(["auto", "manual"])]

# Get unique internal product IDs that have matches
valid_internal_ids = valid_matches["internal_product_id"].unique()

# Build a mapping from internal product ID to product name for the dropdown
id_to_name = dict(zip(products_df["product_id"], products_df["product_name"]))
valid_products = [(pid, id_to_name.get(pid, pid)) for pid in valid_internal_ids if pid in id_to_name]

# Sort by name for easier navigation
valid_products_sorted = sorted(valid_products, key=lambda x: x[1])

# Create selectbox: label shows product name, but we need the ID for lookup
selected_product_name = st.selectbox(
    "Select Internal Product",
    options=[name for _, name in valid_products_sorted],
    index=0
)

# Find the corresponding internal_product_id
selected_product_id = next(pid for pid, name in valid_products_sorted if name == selected_product_name)

# ---------- Fetch specific history ----------
# Get all competitor matches for the selected internal product
selected_matches = valid_matches[valid_matches["internal_product_id"] == selected_product_id]

# Extract competitor and competitor product names
competitor_names = selected_matches["competitor"].unique()
competitor_product_names = selected_matches["competitor_product_name"].unique()

# Filter price_history for those competitor-product combinations
history_filtered = price_history_df[
    (price_history_df["competitor"].isin(competitor_names)) &
    (price_history_df["product_name"].isin(competitor_product_names))
].copy()

# Sort by scraped_at for clean time series
history_filtered["scraped_at"] = pd.to_datetime(history_filtered["scraped_at"])
history_filtered = history_filtered.sort_values("scraped_at")

# Get internal cost and selling price for the selected product
selected_product = products_df[products_df["product_id"] == selected_product_id].iloc[0]
internal_cost = selected_product["cost"]
internal_selling_price = selected_product["selling_price"]

# ---------- Build Plotly line chart ----------
if not history_filtered.empty:
    fig = px.line(
        history_filtered,
        x="scraped_at",
        y="price",
        color="competitor",
        markers=True,
        title=f"Competitor Price History: {selected_product_name}",
        labels={"scraped_at": "Date", "price": "Price ($)", "competitor": "Competitor"}
    )

    # Add internal cost and selling price reference lines
    fig.add_hline(
        y=internal_cost,
        line_dash="dash",
        line_color="red",
        annotation_text="OUR COST",
        annotation_position="bottom right"
    )
    fig.add_hline(
        y=internal_selling_price,
        line_dash="dot",
        line_color="green",
        annotation_text="OUR PRICE",
        annotation_position="top right"
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Price ($)",
        height=600,
        margin=dict(l=0, r=0, t=40, b=0)
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No price history found for the selected product. Please run the scraper first.")

# ---------- Show internal product details ----------
st.markdown("### Internal Product Details")
st.write(f"**Product ID:** {selected_product_id}")
st.write(f"**Product Name:** {selected_product_name}")
st.write(f"**Cost:** ${internal_cost:.2f}")
st.write(f"**Selling Price:** ${internal_selling_price:.2f}")

# ---------- Show matched competitor products ----------
st.markdown("### Matched Competitor Products")
if not selected_matches.empty:
    st.dataframe(selected_matches[["competitor", "competitor_product_name", "match_score", "status"]])
else:
    st.info("No matches for this product.")