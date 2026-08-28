import sys
from pathlib import Path

# Add project root to sys.path so we can import analytics modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

import logging
import sqlite3
import pandas as pd

from analytics.profitability_analysis import run_profitability_analysis
from analytics.score_customers import score_all_customers
from analytics.margin_alerts import detect_margin_breaches
from analytics.alert_dispatcher import dispatch_alerts

# ---------- Logging setup ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/master_pipeline.log")
    ]
)
logger = logging.getLogger("master_pipeline")
logger.propagate = False

DB_PATH = "database/competitor_data.db"

def executive_summary():
    """Print a high-level business summary after both stages succeed."""
    conn = sqlite3.connect(DB_PATH)

    # Profitability headline
    prof_df = pd.read_sql_query("SELECT * FROM product_profitability", conn)
    total_revenue = prof_df["total_revenue"].sum()
    total_profit = prof_df["total_profit"].sum()
    overall_margin = (total_profit / total_revenue * 100) if total_revenue else 0
    bleeders = prof_df[prof_df["total_profit"] < 0]

    # Risk headline
    risk_df = pd.read_sql_query("SELECT * FROM customer_risk_scores", conn)
    high_risk = risk_df[risk_df["risk_flag"] == "HIGH"]
    top5_high = high_risk.sort_values("churn_probability", ascending=False).head(5)

    conn.close()

    print("\n" + "="*70)
    print("EXECUTIVE SUMMARY")
    print("="*70)
    print(f"Total Revenue: ${total_revenue:,.2f}")
    print(f"Overall Margin: {overall_margin:.2f}%")
    print(f"Bleeding Products: {len(bleeders)}")
    print(f"High-Risk Customers: {len(high_risk)}")
    print("\nTop 5 At-Risk Customers:")
    if not top5_high.empty:
        print(top5_high[["customer_id", "name", "region", "churn_probability"]].to_string(index=False))
    else:
        print("None found.")
    print("="*70)

def main():
    logger.info("Starting master pipeline...")

    # Stage 1: Profitability
    try:
        logger.info("Stage 1: Refreshing profitability analysis...")
        run_profitability_analysis()
        logger.info("Stage 1 completed successfully.")
    except Exception as e:
        logger.critical(f"Stage 1 failed: {e}", exc_info=True)
        logger.warning("Continuing to Stage 2 despite failure.")

    # Stage 2: Churn scoring
    try:
        logger.info("Stage 2: Scoring customer churn risk...")
        score_all_customers()
        logger.info("Stage 2 completed successfully.")
    except Exception as e:
        logger.critical(f"Stage 2 failed: {e}", exc_info=True)

    # Stage 3: Margin breach detection
    try:
        logger.info("Stage 3: Refreshing margin breach alerts...")
        breaches, new, updated = detect_margin_breaches()
        logger.info(f"Stage 3 completed: {breaches} breaches, {new} new, {updated} updated.")
    except Exception as e:
        logger.critical(f"Stage 3 failed: {e}", exc_info=True)

    # Stage 4: Dispatch alerts
    try:
        logger.info("Stage 4: Dispatching margin breach alerts...")
        dispatch_alerts()
        logger.info("Stage 4 completed successfully.")
    except Exception as e:
        logger.critical(f"Stage 4 failed: {e}", exc_info=True)

    # Executive summary (if at least one stage succeeded)
    try:
        executive_summary()
    except Exception as e:
        logger.error(f"Could not generate executive summary: {e}")

    logger.info("Master pipeline finished.")

if __name__ == "__main__":
    main()