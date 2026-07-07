"""
Weekly Scheduler
-------------------
Uses APScheduler's CronTrigger (parsed from WEEKLY_CRON, default:
pipeline automatically, so no one has to remember to run it manually.
"""
from __future__ import annotations
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import timezone

from app.config import settings
from app.pipeline import run_full_audit

logger = logging.getLogger("scheduler")

# Run in UTC timezone explicitly to avoid pytz/local tz resolution issues.
scheduler = BackgroundScheduler(timezone=timezone.utc)

def _cron_trigger_from_string(cron_str: str) -> CronTrigger:
    minute, hour, day, month, day_of_week = cron_str.split()
    return CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, timezone=timezone.utc)

def _safe_run_audit():
    try:
        logger.info("Scheduler triggered automatic audit job.")
        run_full_audit(send_email=True)
    except Exception as exc:
        logger.error("Scheduled audit job failed: %s", exc, exc_info=True)

def start_scheduler():
    if settings.SCHEDULER_TEST_MODE:
        trigger = IntervalTrigger(minutes=1, timezone=timezone.utc)
        logger.info("Scheduler started in TESTING MODE (runs every 1 minute).")
    else:
        trigger = _cron_trigger_from_string(settings.WEEKLY_CRON)
        logger.info("Scheduler started. Weekly audit cron: %s", settings.WEEKLY_CRON)

    scheduler.add_job(
        func=_safe_run_audit,
        trigger=trigger,
        id="weekly_website_audit",
        replace_existing=True,
    )
    
    scheduler.start()
    
    # Print next run time
    job = scheduler.get_job("weekly_website_audit")
    if job and job.next_run_time:
        logger.info("Next scheduled run time: %s", job.next_run_time)


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
