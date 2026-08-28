import sqlite3
import logging
from datetime import datetime
from pathlib import Path

DB_PATH = Path("database/competitor_data.db")

# ---------- Logger setup ----------
logger = logging.getLogger("margin_alerts")
logger.setLevel(logging.INFO)
logger.propagate = False  # prevent duplicate logs when called from pipeline
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def detect_margin_breaches():
    """Query v_master_intelligence for matched products, flag breaches, and update audit table."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()

    # Ensure alert table exists, including notified_at column
    cur.execute("""
        CREATE TABLE IF NOT EXISTS margin_breach_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            internal_product_id TEXT,
            competitor TEXT,
            competitor_product TEXT,
            competitor_price REAL,
            our_cost REAL,
            breach_depth REAL,
            breach_pct REAL,
            first_detected_at TEXT,
            last_seen_at TEXT,
            status TEXT DEFAULT 'new',
            notified_at TEXT
        )
    """)

    # Query matched rows from master view
    cur.execute("""
        SELECT
            internal_product_id,
            competitor,
            competitor_product_name,
            latest_price,
            unit_cost
        FROM v_master_intelligence
        WHERE internal_product_id IS NOT NULL
          AND latest_price IS NOT NULL
          AND unit_cost IS NOT NULL
    """)
    matched_rows = cur.fetchall()

    breaches_detected = 0
    new_alerts = 0
    updated_existing = 0

    for internal_id, comp, comp_name, latest_price, unit_cost in matched_rows:
        if latest_price < unit_cost:
            breach_depth = unit_cost - latest_price
            breach_pct = (breach_depth / unit_cost) * 100 if unit_cost else 0

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Check for existing open alert (status 'new' or 'sent')
            cur.execute("""
                SELECT alert_id, status FROM margin_breach_alerts
                WHERE internal_product_id = ? AND competitor = ?
                  AND status IN ('new', 'sent')
            """, (internal_id, comp))
            existing = cur.fetchone()

            if existing:
                alert_id, current_status = existing
                # Update last_seen_at and current competitor price
                cur.execute("""
                    UPDATE margin_breach_alerts
                    SET last_seen_at = ?, competitor_price = ?
                    WHERE alert_id = ?
                """, (now_str, latest_price, alert_id))
                updated_existing += 1
            else:
                # Insert new alert
                cur.execute("""
                    INSERT INTO margin_breach_alerts
                    (internal_product_id, competitor, competitor_product, competitor_price,
                     our_cost, breach_depth, breach_pct, first_detected_at, last_seen_at,
                     status, notified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', NULL)
                """, (internal_id, comp, comp_name, latest_price, unit_cost,
                      breach_depth, breach_pct, now_str, now_str))
                new_alerts += 1

            breaches_detected += 1
            logger.info(f"[BREACH] {internal_id} vs {comp} {comp_name}: our cost ${unit_cost:.2f} > competitor ${latest_price:.2f} (breach ${breach_depth:.2f}, {breach_pct:.1f}%)")
        else:
            # Optional: log squeeze cases (small positive margin)
            squeeze_threshold = 1.50  # dollars
            if 0 < (latest_price - unit_cost) <= squeeze_threshold:
                logger.info(f"[SQUEEZE] {internal_id} vs {comp} {comp_name}: margin only ${latest_price - unit_cost:.2f}")

    conn.commit()
    conn.close()

    logger.info(f"Margin alert run complete: {breaches_detected} breaches detected, {new_alerts} new, {updated_existing} updated.")
    return breaches_detected, new_alerts, updated_existing

if __name__ == "__main__":
    detect_margin_breaches()