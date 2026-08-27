import sqlite3
import pandas as pd
from datetime import timedelta

DB_PATH = "database/competitor_data.db"

def compute_customer_features(orders_df, as_of_date):
    """
    Given a DataFrame of orders (with columns: customer_id, order_id, order_date, quantity, unit_price),
    compute RFM features for each customer as of the given date.
    Returns a DataFrame with columns:
        customer_id, recency_days, frequency, monetary_avg, tenure_days, purchase_rhythm, recent_activity
    """
    # Ensure order_date is datetime
    orders_df = orders_df.copy()
    orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])
    
    # Filter orders up to the as_of_date
    history = orders_df[orders_df["order_date"] <= as_of_date]
    
    # Compute line_total for monetary
    history["line_total"] = history["quantity"] * history["unit_price"]
    
    # Group by customer
    grouped = history.groupby("customer_id").agg(
        last_order=("order_date", "max"),
        first_order=("order_date", "min"),
        frequency=("order_id", "count"),
        total_spend=("line_total", "sum")
    ).reset_index()
    
    # Recency
    grouped["recency_days"] = (as_of_date - grouped["last_order"]).dt.days
    # Tenure
    grouped["tenure_days"] = (as_of_date - grouped["first_order"]).dt.days
    # Monetary average
    grouped["monetary_avg"] = grouped["total_spend"] / grouped["frequency"]
    # Purchase rhythm: average days between orders (avoid div by zero)
    grouped["purchase_rhythm"] = grouped["tenure_days"] / (grouped["frequency"] - 1).replace(0, 1)
    # For frequency=1, set rhythm = tenure (effective gap is entire tenure)
    grouped.loc[grouped["frequency"] == 1, "purchase_rhythm"] = grouped["tenure_days"]
    
    # Recent activity: orders in the 90 days before as_of_date
    recent_start = as_of_date - timedelta(days=90)
    recent = history[history["order_date"] >= recent_start]
    recent_counts = recent.groupby("customer_id").size().reset_index(name="recent_activity")
    grouped = grouped.merge(recent_counts, on="customer_id", how="left")
    grouped["recent_activity"] = grouped["recent_activity"].fillna(0).astype(int)
    
    # Keep only required columns
    feature_cols = ["customer_id", "recency_days", "frequency", "monetary_avg", "tenure_days", "purchase_rhythm", "recent_activity"]
    return grouped[feature_cols]

def run_churn_feature_engineering():
    """Build RFM features for training using the snapshot anti-leakage method."""
    conn = sqlite3.connect(DB_PATH)
    orders_df = pd.read_sql_query("SELECT * FROM internal_orders", conn)
    customers_df = pd.read_sql_query("SELECT * FROM internal_customers", conn)
    conn.close()
    
    orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])
    CURRENT_DATE = orders_df["order_date"].max()
    SNAPSHOT_DATE = CURRENT_DATE - timedelta(days=90)
    print(f"Current date: {CURRENT_DATE.date()}")
    print(f"Snapshot date: {SNAPSHOT_DATE.date()}")
    
    # Split orders into history and window
    history_orders = orders_df[orders_df["order_date"] <= SNAPSHOT_DATE]
    window_orders = orders_df[orders_df["order_date"] > SNAPSHOT_DATE]
    print(f"History orders (<= snapshot): {len(history_orders)}")
    print(f"Window orders (> snapshot): {len(window_orders)}")
    
    # Compute features on history
    features = compute_customer_features(history_orders, SNAPSHOT_DATE)
    
    # Build label: churned = 1 if no order in window
    window_customers = window_orders["customer_id"].unique()
    features["churned"] = (~features["customer_id"].isin(window_customers)).astype(int)
    
    # Merge region for metadata
    features = features.merge(customers_df[["customer_id", "region"]], on="customer_id", how="left")
    
    # Drop customers with no history orders? compute_customer_features already only includes those with history
    # Print churn rate
    churn_rate = features["churned"].mean() * 100
    print(f"\nChurn rate: {churn_rate:.2f}%")
    
    # Save to SQLite and CSV
    conn = sqlite3.connect(DB_PATH)
    features.to_sql("customer_churn_features", conn, if_exists="replace", index=False)
    conn.close()
    features.to_csv("data/customer_churn_features.csv", index=False)
    print("Saved training features to 'customer_churn_features' and CSV.")
    
    # Sanity samples
    print("\nSample of churned:")
    print(features[features["churned"]==1].head(3))
    print("\nSample of retained:")
    print(features[features["churned"]==0].head(3))

if __name__ == "__main__":
    run_churn_feature_engineering()