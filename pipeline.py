"""
pipeline.py — Master orchestrator.
Runs the full scrape → summarize → format → quality gate → send loop.
Designed to be called by cron daily at 7am CT.

Usage:
  python pipeline.py            # run once now
  python pipeline.py --schedule # run on schedule (keeps process alive)
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import schedule
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ─── Configure logging ───────────────────────────────────────────────────────
LOG_PATH = os.environ.get("LOG_PATH", "./logs/rcmaas.log")
os.makedirs("./logs", exist_ok=True)
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
logger.add(LOG_PATH, rotation="7 days", retention="30 days",
           level="DEBUG", format="{time} | {level} | {message}")

# ─── Import modules ───────────────────────────────────────────────────────────
from scraper   import run_scraper
from summarizer import Summarizer
from formatter  import format_digest
from sender     import send_beehiiv_post, telegram_alert, get_subscriber_count, DRY_RUN


# ─────────────────────────────────────────────────────────────────────────────
# Core pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline():
    start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"Pipeline started at {start.strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info(f"DRY_RUN = {DRY_RUN}")
    logger.info("=" * 60)

    try:
        # ── Step 1: Scrape all sources ────────────────────────────────────────
        logger.info("STEP 1 — Scraping sources...")
        new_items = run_scraper(
            sources_path=os.environ.get("SOURCES_PATH", "./sources.yaml"),
            db_path=os.environ.get("DB_PATH", "./data/rcmaas.db"),
        )

        if not new_items:
            logger.info("No new items found today. Pipeline exiting early.")
            telegram_alert(
                f"📭 *RCMaaS Daily Run — {start.strftime('%b %-d')}*\n"
                f"No new regulatory items found. No digest sent."
            )
            return

        logger.info(f"Found {len(new_items)} new items.")

        # ── Step 2: Summarize with Claude ─────────────────────────────────────
        logger.info("STEP 2 — Summarizing with Claude...")
        summarizer = Summarizer()
        package = summarizer.build_digest(new_items)

        logger.info(f"Digest: {len(package.items)} items, "
                    f"quality {package.quality_score}/10, "
                    f"send={package.send_recommended}")

        # ── Step 3: Quality gate ──────────────────────────────────────────────
        if not package.send_recommended:
            logger.warning(
                f"Quality gate BLOCKED send. Score={package.quality_score}. "
                f"Notes: {package.quality_notes}"
            )
            telegram_alert(
                f"⚠️ *RCMaaS Quality Gate Blocked Send*\n"
                f"Score: {package.quality_score}/10\n"
                f"Reason: {package.quality_notes}\n"
                f"Items found: {len(package.items)}\n\n"
                f"Review manually and set `FORCE_SEND=true` if OK."
            )
            # If forced override via env var
            if os.environ.get("FORCE_SEND", "false").lower() != "true":
                return

        # ── Step 4: Format email ──────────────────────────────────────────────
        logger.info("STEP 3 — Formatting email...")
        subject, html, plain = format_digest(package)
        logger.info(f"Subject: {subject}")

        # ── Step 5: Send via Beehiiv ──────────────────────────────────────────
        logger.info("STEP 4 — Sending via Beehiiv...")
        result = send_beehiiv_post(subject, html, plain)

        # ── Step 6: Telegram summary to you ──────────────────────────────────
        elapsed = (datetime.now(timezone.utc) - start).seconds
        sub_count = get_subscriber_count()

        action_items = sum(
            1 for i in package.items if i.urgency == "Action required"
        )
        monitor_items = sum(
            1 for i in package.items if i.urgency == "Monitor"
        )

        send_status = "✅ SENT" if not DRY_RUN else "🔵 DRY RUN (not sent)"
        top_headlines = "\n".join(
            f"  • [{i.urgency}] {i.headline[:70]}"
            for i in package.items[:5]
        )

        telegram_alert(
            f"{send_status} — *Immigration Compliance Digest*\n"
            f"📅 {start.strftime('%B %-d, %Y')}\n\n"
            f"📊 *Stats:*\n"
            f"  • {len(package.items)} items in digest\n"
            f"  • ⚠️ {action_items} action required\n"
            f"  • 📌 {monitor_items} to monitor\n"
            f"  • Quality score: {package.quality_score}/10\n"
            f"  • Subscribers: {sub_count}\n"
            f"  • Runtime: {elapsed}s\n\n"
            f"📋 *Top items:*\n{top_headlines}"
        )

        logger.success("Pipeline completed successfully.")

    except Exception as e:
        logger.exception(f"Pipeline FAILED: {e}")
        telegram_alert(
            f"🚨 *RCMaaS Pipeline Error*\n"
            f"Error: `{str(e)[:200]}`\n"
            f"Check logs at: {LOG_PATH}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry points
# ─────────────────────────────────────────────────────────────────────────────

def run_scheduled():
    """Run on a daily schedule (keeps process alive)."""
    tz    = os.environ.get("TIMEZONE", "America/Chicago")
    hour  = int(os.environ.get("DIGEST_SEND_HOUR", 7))

    logger.info(f"Scheduler starting — will run daily at {hour:02d}:00 ({tz})")
    schedule.every().day.at(f"{hour:02d}:00").do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RCMaaS Pipeline")
    parser.add_argument(
        "--schedule", action="store_true",
        help="Run on daily schedule (keeps process alive). "
             "Default: run once and exit."
    )
    args = parser.parse_args()

    if args.schedule:
        run_scheduled()
    else:
        run_pipeline()
