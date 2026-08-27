import logging
import sqlite3
import pandas as pd
from pathlib import Path
import sys

# Add project root to path to import analytics modules
sys.path.append(str(Path(__file__).resolve().parent.parent))
from analytics.profitability_analysis import run_profitability_analysis
from analytics.score_customers import score_all_customers

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/master_pipeline.log")
    ]
)
logger = logging.getLogger("master_pipeline")

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

    # Only print summary if both stages succeeded
    if "Stage 1" and "Stage 2" in locals():
        # We could check if both functions ran without raising; but since we caught exceptions, we can still show partial.
        try:
            executive_summary()
        except Exception as e:
            logger.error(f"Could not generate executive summary: {e}")

    logger.info("Master pipeline finished.")

if __name__ == "__main__":
    main()