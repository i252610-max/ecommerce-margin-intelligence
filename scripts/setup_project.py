import sqlite3
import subprocess
import sys
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_project")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "competitor_data.db"
SEED_CSV = PROJECT_ROOT / "data" / "price_history_seed.csv"

def run_script(script_path):
    """Run a Python script and check for errors."""
    logger.info(f"Running {script_path.name}...")
    result = subprocess.run([sys.executable, str(script_path)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Failed: {script_path}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
        raise RuntimeError(f"Script {script_path} failed")
    logger.info(f"Completed {script_path.name}")

def table_exists_and_not_empty(table_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if cur.fetchone() is None:
        conn.close()
        return False
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    conn.close()
    return count > 0

def seed_price_history():
    if table_exists_and_not_empty("price_history"):
        logger.info("price_history already has data — skipping seed.")
        return
    if not SEED_CSV.exists():
        logger.warning("Seed CSV not found. Live scraping will be needed to populate price_history.")
        return
    import pandas as pd
    df = pd.read_csv(SEED_CSV)
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("price_history", conn, if_exists="append", index=False)
    conn.close()
    logger.info(f"Loaded {len(df)} rows into price_history from seed CSV.")

def main():
    logger.info("Starting project setup...")

    # 1. Internal data: synthetic generator if missing/empty
    if not table_exists_and_not_empty("internal_orders"):
        logger.info("Generating synthetic internal data...")
        run_script(PROJECT_ROOT / "scripts" / "generate_synthetic_data.py")
    else:
        logger.info("Internal data already present — skipping generator.")

    # 2. Competitor history: seed if empty
    seed_price_history()

    # 3. Views: always rebuild (cheap)
    run_script(PROJECT_ROOT / "scripts" / "build_views.py")

    # 4. Matches: manual seed if product_matches empty
    if not table_exists_and_not_empty("product_matches"):
        logger.info("Seeding manual matches...")
        run_script(PROJECT_ROOT / "scripts" / "seed_matches.py")
    else:
        logger.info("product_matches already has data — skipping manual seed.")

    # 5. ML: features and model
    run_script(PROJECT_ROOT / "analytics" / "churn_features.py")
    run_script(PROJECT_ROOT / "analytics" / "churn_model_final.py")

    # 6. Pipeline (includes export, alerts, scoring)
    run_script(PROJECT_ROOT / "scripts" / "run_pipeline.py")

    logger.info("✅ Setup completed successfully.")

if __name__ == "__main__":
    main()