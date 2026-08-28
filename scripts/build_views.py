import sqlite3
from pathlib import Path

DB_PATH = Path("database/competitor_data.db")
SQL_PATH = Path("database/master_views.sql")

def build_views():
    conn = sqlite3.connect(DB_PATH)
    try:
        with open(SQL_PATH, "r", encoding="utf-8") as f:
            sql_script = f.read()
        conn.executescript(sql_script)
        conn.commit()
        print(" Views and bridge table built successfully.")
    except Exception as e:
        conn.rollback()
        print(f" Error building views: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    build_views()