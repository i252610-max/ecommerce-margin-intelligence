import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("database/competitor_data.db")
OUTPUT_PATH = Path("data/price_history_seed.csv")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("SELECT * FROM price_history", conn)
conn.close()
df.to_csv(OUTPUT_PATH, index=False)
print(f"✅ Exported {len(df)} rows to {OUTPUT_PATH}")