import sqlite3
from pathlib import Path

conn = sqlite3.connect(Path("database/competitor_data.db"))
cur = conn.cursor()
cur.execute("DELETE FROM product_matches;")
cur.execute("DELETE FROM margin_breach_alerts;")
conn.commit()
conn.close()
print("Cleared product_matches and margin_breach_alerts.")