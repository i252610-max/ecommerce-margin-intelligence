import sqlite3
from pathlib import Path

# Determine the database file path relative to this file
DB_PATH = Path(__file__).resolve().parent / "competitor_data.db"

def init_db():
    """
    Create the price_history table if it doesn't exist.
    Call this once at the start of the scraper to ensure the table is ready.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competitor TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            scraped_at DATETIME NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def insert_products(products_list):
    """
    Insert a list of product tuples into price_history.
    Each tuple should be (competitor, product_name, price, scraped_at).
    Uses executemany() for efficient bulk insert.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    sql = """
        INSERT INTO price_history (competitor, product_name, price, scraped_at)
        VALUES (?, ?, ?, ?)
    """
    cursor.executemany(sql, products_list)
    conn.commit()
    conn.close()