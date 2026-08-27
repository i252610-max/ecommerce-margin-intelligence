import sqlite3
import pandas as pd

DB_PATH = "database/competitor_data.db"   # adjust if running from project root

def run_profitability_analysis():
    """Load data, calculate per-product profitability, save and print report."""
    # --- Step 2: Load data into DataFrames ---
    conn = sqlite3.connect(DB_PATH)
    orders_df = pd.read_sql_query("SELECT * FROM internal_orders", conn)
    products_df = pd.read_sql_query("SELECT * FROM internal_products", conn)
    conn.close()

    # Verify inputs
    print("Orders shape:", orders_df.shape)
    print("Products shape:", products_df.shape)
    print("\nOrders head:")
    print(orders_df.head())
    print("\nProducts head:")
    print(products_df.head())

    # --- Step 3: Join and line-item economics ---
    # Merge orders with products on product_id
    merged = orders_df.merge(products_df, on="product_id", how="left")

    # Calculate line-level metrics
    merged["line_revenue"] = merged["quantity"] * merged["unit_price"]
    merged["line_cost"] = merged["quantity"] * merged["cost"]
    merged["line_profit"] = merged["line_revenue"] - merged["line_cost"]

    # --- Step 4: Aggregate per product ---
    product_agg = merged.groupby(["product_id", "product_name"]).agg(
        total_units=("quantity", "sum"),
        total_revenue=("line_revenue", "sum"),
        total_cost=("line_cost", "sum"),
        total_profit=("line_profit", "sum"),
        unit_cost=("cost", "first")   # add unit cost for Phase 3
    ).reset_index()

    # Calculate gross margin %, guard against division by zero
    product_agg["gross_margin_pct"] = (product_agg["total_profit"] / product_agg["total_revenue"]) * 100
    product_agg["gross_margin_pct"] = product_agg["gross_margin_pct"].fillna(0)
    # If revenue is zero, set margin to 0
    product_agg.loc[product_agg["total_revenue"] == 0, "gross_margin_pct"] = 0

    # Sort by total profit descending
    product_agg = product_agg.sort_values("total_profit", ascending=False)

    # --- Print business report ---
    print("\n" + "="*60)
    print("PROFITABILITY REPORT")
    print("="*60)

    # Overall headline
    total_revenue = product_agg["total_revenue"].sum()
    total_profit = product_agg["total_profit"].sum()
    overall_margin = (total_profit / total_revenue * 100) if total_revenue else 0
    num_unprofitable = (product_agg["total_profit"] < 0).sum()
    print(f"Total revenue: ${total_revenue:,.2f} | Overall margin: {overall_margin:.2f}% | {num_unprofitable} products are currently unprofitable.\n")

    # Top 5 profit drivers
    print("TOP 5 PROFIT DRIVERS:")
    print(product_agg.head(5)[["product_name", "total_units", "total_revenue", "total_profit", "gross_margin_pct"]].to_string(index=False))

    # Bottom 5 money bleeders
    print("\nBOTTOM 5 MONEY BLEEDERS:")
    bottom_5 = product_agg.tail(5).sort_values("total_profit")   # ascending for worst first
    print(bottom_5[["product_name", "total_units", "total_revenue", "total_profit", "gross_margin_pct"]].to_string(index=False))

    # --- Step 5: Save to SQLite ---
    conn = sqlite3.connect(DB_PATH)
    # Ensure cost column is included for future alerting
    product_agg.to_sql("product_profitability", conn, if_exists="replace", index=False)
    conn.close()
    print("\nAnalysis saved to 'product_profitability' table.")

if __name__ == "__main__":
    run_profitability_analysis()