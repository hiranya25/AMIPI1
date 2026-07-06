"""
Weekly Scheduler
-------------------
Uses APScheduler's CronTrigger (parsed from WEEKLY_CRON, default:
"0 6 * * MON" — every Monday 6:00 AM) to trigger the full audit
pipeline automatically, so no one has to remember to run it manually.
"""
from __future__ import annotations
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.pipeline import run_full_audit

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()


def _cron_trigger_from_string(cron_str: str) -> CronTrigger:
    minute, hour, day, month, day_of_week = cron_str.split()
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)


def start_scheduler():
    trigger = _cron_trigger_from_string(settings.WEEKLY_CRON)
    scheduler.add_job(
        func=lambda: run_full_audit(send_email=True),
        trigger=trigger,
        id="weekly_website_audit",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started. Weekly audit cron: %s", settings.WEEKLY_CRON)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
