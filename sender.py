"""
sender.py — Sends the formatted digest via Beehiiv API and
alerts you on Telegram with every key event.
"""

import os
import requests
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

BEEHIIV_API_KEY       = os.environ.get("BEEHIIV_API_KEY", "")
BEEHIIV_PUB_ID        = os.environ.get("BEEHIIV_PUBLICATION_ID", "")
TELEGRAM_BOT_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID      = os.environ.get("TELEGRAM_CHAT_ID", "")
DRY_RUN               = os.environ.get("DRY_RUN", "true").lower() == "true"


# ─────────────────────────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────────────────────────

def telegram_alert(message: str):
    """Send a Telegram message to you (the operator)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured, skipping alert.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
        }, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram alert sent.")
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Beehiiv
# ─────────────────────────────────────────────────────────────────────────────

def send_beehiiv_post(
    subject: str,
    html_body: str,
    plain_body: str,
    subtitle: str = "Daily immigration compliance update for HR teams",
) -> dict:
    """
    Creates and publishes a post to all active subscribers via Beehiiv API.
    Docs: https://developers.beehiiv.com/docs/v2/
    """
    if DRY_RUN:
        logger.warning("DRY_RUN=true — email NOT sent. Preview logged only.")
        logger.info(f"[DRY RUN] Subject: {subject}")
        logger.info(f"[DRY RUN] HTML length: {len(html_body)} chars")
        return {"dry_run": True, "subject": subject}

    if not BEEHIIV_API_KEY or not BEEHIIV_PUB_ID:
        logger.error("Beehiiv credentials not set.")
        return {"error": "missing_credentials"}

    url = f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/posts"
    headers = {
        "Authorization": f"Bearer {BEEHIIV_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "subject_line":       subject,
        "subtitle":           subtitle,
        "content_html":       html_body,
        "content_text":       plain_body,
        "status":             "confirmed",       # publish immediately
        "send_at":            None,              # send now
        "audience":           "free",            # free tier subs
        "content_tags":       ["immigration", "hr", "compliance"],
        "preview_text":       subject[:90],
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        logger.success(f"Beehiiv post created: {data.get('data', {}).get('id')}")
        return data
    except Exception as e:
        logger.error(f"Beehiiv send failed: {e}")
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Subscriber management helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_subscriber_count() -> int:
    """Fetch current active subscriber count from Beehiiv."""
    if not BEEHIIV_API_KEY or not BEEHIIV_PUB_ID:
        return 0
    try:
        url = f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/subscriptions"
        headers = {"Authorization": f"Bearer {BEEHIIV_API_KEY}"}
        resp = requests.get(url, params={"status": "active", "limit": 1},
                            headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("total_results", 0)
    except Exception as e:
        logger.error(f"Subscriber count failed: {e}")
        return -1


if __name__ == "__main__":
    telegram_alert(
        "🤖 *RCMaaS Test Alert*\n"
        "Pipeline is up and Telegram alerts are working correctly."
    )
    print("Telegram test sent (check your phone).")
    print(f"DRY_RUN = {DRY_RUN}")
    print(f"Subscriber count: {get_subscriber_count()}")
