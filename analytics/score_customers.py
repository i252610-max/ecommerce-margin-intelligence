import sqlite3
import joblib
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Import the feature function from churn_features module
import sys
sys.path.append(str(Path(__file__).resolve().parent))
from churn_features import compute_customer_features

DB_PATH = "database/competitor_data.db"
MODEL_PATH = "models/churn_pipeline.pkl"

def score_all_customers():
    """Load pipeline, compute current features, score churn risk, write to customer_risk_scores."""
    # Load orders and customers
    conn = sqlite3.connect(DB_PATH)
    orders_df = pd.read_sql_query("SELECT * FROM internal_orders", conn)
    customers_df = pd.read_sql_query("SELECT customer_id, name, region FROM internal_customers", conn)
    conn.close()

    # Define current date as max order date (or today's date)
    orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])
    CURRENT_DATE = orders_df["order_date"].max()  # or datetime.now().date()
    # For scoring, we compute features as of CURRENT_DATE
    features = compute_customer_features(orders_df, CURRENT_DATE)

    # Load pipeline
    pipeline = joblib.load(MODEL_PATH)

    # Predict probabilities
    feature_cols = ["recency_days", "frequency", "monetary_avg", "tenure_days", "purchase_rhythm", "recent_activity"]
    X = features[feature_cols]
    churn_proba = pipeline.predict_proba(X)[:, 1]  # probability of churn (class 1)

    # Build result DataFrame
    features["churn_probability"] = churn_proba
    # Rank-based tiers: top 15% HIGH, next 25% MEDIUM, rest LOW
    # This is a business decision, not a statistical absolute.
    pct_rank = features["churn_probability"].rank(pct=True, method="first")
    features["risk_flag"] = pd.cut(
        pct_rank,
        bins=[0, 0.60, 0.85, 1.0],   # 0-60% LOW, 60-85% MEDIUM, 85-100% HIGH
        labels=["LOW", "MEDIUM", "HIGH"],
        include_lowest=True
    )
    features["scored_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Merge customer name and region
    result = features.merge(customers_df, on="customer_id", how="left")

    # Save to SQLite (replace table)
    conn = sqlite3.connect(DB_PATH)
    result.to_sql("customer_risk_scores", conn, if_exists="replace", index=False)
    conn.close()
    print("✅ Customer risk scores saved to 'customer_risk_scores' table.")
    return result

if __name__ == "__main__":
    score_all_customers()