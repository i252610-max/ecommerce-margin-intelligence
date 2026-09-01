import sqlite3
import pandas as pd
from pathlib import Path

# Determine project root (one level up from scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "competitor_data.db"
OUTPUT_DIR = PROJECT_ROOT / "dashboard" / "pbi_data"

# Ensure output directory exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def export_for_pbi():
    """Export core analytical tables to CSV for Power BI consumption."""
    conn = sqlite3.connect(DB_PATH)

    # 1. Master intelligence view
    master_intel = pd.read_sql_query("SELECT * FROM v_master_intelligence", conn)
    master_intel.to_csv(OUTPUT_DIR / "master_intelligence.csv", index=False)

    # 2. Customer risk scores
    customer_risk = pd.read_sql_query("SELECT * FROM customer_risk_scores", conn)
    customer_risk.to_csv(OUTPUT_DIR / "customer_risk.csv", index=False)

    # 3. Product profitability
    profitability = pd.read_sql_query("SELECT * FROM product_profitability", conn)
    profitability.to_csv(OUTPUT_DIR / "profitability.csv", index=False)

    # 4. Active margin breach alerts (exclude rejected)
    active_alerts = pd.read_sql_query("""
        SELECT * FROM margin_breach_alerts
        WHERE status != 'rejected'
    """, conn)
    active_alerts.to_csv(OUTPUT_DIR / "active_alerts.csv", index=False)

    conn.close()
    print(f"✅ Exported analytical data to {OUTPUT_DIR}")

if __name__ == "__main__":
    export_for_pbi()