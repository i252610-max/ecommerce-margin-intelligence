import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

DB_PATH = Path("database/competitor_data.db")

# ---------- Logger setup ----------
logger = logging.getLogger("alert_dispatcher")
logger.setLevel(logging.INFO)
logger.propagate = False  # prevent duplicate logs when called from pipeline
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def dispatch_alerts():
    """Send new margin breach alerts via Discord webhook and update status."""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("No webhook configured — skipping dispatch.")
        return

    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.cursor()

    # Fetch alerts that have not yet been dispatched
    cur.execute("""
        SELECT alert_id, internal_product_id, competitor, competitor_product,
               competitor_price, our_cost, breach_depth, breach_pct
        FROM margin_breach_alerts
        WHERE status = 'new'
    """)
    new_alerts = cur.fetchall()

    if not new_alerts:
        logger.info("No new alerts to dispatch.")
        conn.close()
        return

    for alert in new_alerts:
        (alert_id, internal_id, comp, comp_name,
         comp_price, our_cost, breach_depth, breach_pct) = alert

        # Determine color based on breach percentage
        color = 0xFF0000 if breach_pct > 25 else 0xFFA500  # red or orange

        embed = {
            "title": "[BREACH] Margin Breach Detected",
            "color": color,
            "fields": [
                {"name": "Internal Product", "value": internal_id, "inline": True},
                {"name": "Competitor", "value": comp, "inline": True},
                {"name": "Competitor Product", "value": comp_name, "inline": False},
                {"name": "Competitor Price", "value": f"${comp_price:.2f}", "inline": True},
                {"name": "Our Cost", "value": f"${our_cost:.2f}", "inline": True},
                {"name": "Breach Depth", "value": f"${breach_depth:.2f} ({breach_pct:.1f}%)", "inline": False},
            ],
            "timestamp": datetime.now().isoformat()
        }

        payload = {"embeds": [embed]}

        try:
            response = requests.post(webhook_url, json=payload)
            # Discord returns 204 No Content on success
            if response.status_code == 204:
                logger.info(f"Alert {alert_id} sent successfully.")
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("""
                    UPDATE margin_breach_alerts
                    SET status = 'sent', notified_at = ?
                    WHERE alert_id = ?
                """, (now_str, alert_id))
            else:
                logger.error(f"Failed to send alert {alert_id}. Status code: {response.status_code}")
                # Leave status as 'new' for retry
        except Exception as e:
            logger.error(f"Exception sending alert {alert_id}: {e}")

    conn.commit()
    conn.close()
    logger.info("Dispatch run completed.")

if __name__ == "__main__":
    dispatch_alerts()