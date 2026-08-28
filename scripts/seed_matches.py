import sqlite3
from pathlib import Path

DB_PATH = Path("database/competitor_data.db")

manual_matches = [
    # Breach 1: gymshark Crest T-Shirt vs P002 (cost 38.68)
    ("P002", "gymshark", "Crest T-Shirt", 100, "manual"),
    # Breach 2: etsy Cthulhu keycaps vs P036 (cost 93.75)
    ("P036", "etsy", "Cthulhu Old God Keycap Set Gothic PBT Full Keycap Set Retro Themed Custom Mechanical Keyboard Keycaps 130 Keys", 100, "manual"),
    # Squeeze (not breach): gymshark Power T-Shirt vs P004 (cost 34.64)
    ("P004", "gymshark", "Power T-Shirt", 100, "manual"),
    # Safe: gymshark Geo Seamless T-Shirt vs P001 (cost 15.88)
    ("P001", "gymshark", "Geo Seamless T-Shirt", 100, "manual"),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Ensure product_matches table exists (it was created by build_views, but just in case)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            internal_product_id TEXT,
            competitor TEXT,
            competitor_product_name TEXT,
            match_score REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    for internal_id, comp, comp_name, score, status in manual_matches:
        # Check if match already exists to avoid duplicates
        cur.execute("""
            SELECT id FROM product_matches
            WHERE internal_product_id = ? AND competitor = ? AND competitor_product_name = ?
        """, (internal_id, comp, comp_name))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO product_matches (internal_product_id, competitor, competitor_product_name, match_score, status)
                VALUES (?, ?, ?, ?, ?)
            """, (internal_id, comp, comp_name, score, status))
    conn.commit()
    conn.close()
    print(" Manual matches seeded.")

if __name__ == "__main__":
    seed()