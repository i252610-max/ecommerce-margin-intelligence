import sqlite3
import logging
from pathlib import Path

DB_PATH = Path("database/competitor_data.db")

# ---------- Tiers (business-tunable) ----------
AUTO_THRESHOLD = 90          # >= 90 -> auto-confirm
REVIEW_THRESHOLD = 70        # 70-89 -> needs_review
# below 70 -> discard

logger = logging.getLogger("promote_matches")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def promote_matches():
    """Promote match_candidates into product_matches based on confidence tiers."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()

    # Ensure product_matches table exists
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

    # Read all candidates
    cur.execute("""
        SELECT internal_product_id, competitor, competitor_product_name, score
        FROM match_candidates
    """)
    candidates = cur.fetchall()

    auto_count = 0
    review_count = 0
    discarded = 0

    for internal_id, comp, comp_name, score in candidates:
        if score >= AUTO_THRESHOLD:
            status = "auto"
            auto_count += 1
        elif score >= REVIEW_THRESHOLD:
            status = "needs_review"
            review_count += 1
        else:
            discarded += 1
            continue

        # Idempotency: check if existing row (any status) exists for same triple
        cur.execute("""
            SELECT id, status FROM product_matches
            WHERE internal_product_id = ? AND competitor = ? AND competitor_product_name = ?
        """, (internal_id, comp, comp_name))
        existing = cur.fetchone()

        if existing:
            existing_id, existing_status = existing
            # Manual rows always win: do not overwrite status
            if existing_status == "manual":
                logger.debug(f"Skipping manual match for {internal_id} vs {comp_name}")
                continue
            # Update score if non-manual
            cur.execute("""
                UPDATE product_matches
                SET match_score = ?, status = ?
                WHERE id = ?
            """, (score, status, existing_id))
        else:
            # Insert new row
            cur.execute("""
                INSERT INTO product_matches
                (internal_product_id, competitor, competitor_product_name, match_score, status)
                VALUES (?, ?, ?, ?, ?)
            """, (internal_id, comp, comp_name, score, status))

    conn.commit()
    conn.close()

    total_promoted = auto_count + review_count
    logger.info(f"Promotion complete: {auto_count} auto, {review_count} needs_review, {discarded} discarded.")
    return auto_count, review_count, discarded

if __name__ == "__main__":
    promote_matches()