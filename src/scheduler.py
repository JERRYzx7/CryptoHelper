"""Scheduler — periodic scan execution using APScheduler."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import AppConfig

logger = logging.getLogger(__name__)


def create_scheduler(
    config: AppConfig,
    scan_func,
    status_func=None,
) -> AsyncIOScheduler:
    """Create and configure the APScheduler instance.

    Parameters
    ----------
    config:
        Application config.
    scan_func:
        Async callable to run on each scan interval (the main scan loop).
    status_func:
        Optional async callable for the fixed-schedule status report.
        Called at hours listed in config.notification.status_schedule_hours (TST).
    """
    scheduler = AsyncIOScheduler()

    # Main scan job — cron at :00, :15, :30, :45 every hour (TST)
    scheduler.add_job(
        scan_func,
        "cron",
        minute="0,15,30,45",
        timezone="Asia/Taipei",
        id="scan",
        name="Market Scan",
        max_instances=1,  # Prevent overlapping scans
    )

    # Status report job — cron at fixed TST hours
    if status_func and config.notification.status_schedule_hours:
        hour_str = ",".join(str(h) for h in config.notification.status_schedule_hours)
        scheduler.add_job(
            status_func,
            "cron",
            hour=hour_str,
            timezone="Asia/Taipei",
            id="status",
            name="Status Report",
        )
        logger.info(
            "Scheduler configured: scan at :00/:15/:30/:45, status at %s TST",
            hour_str,
        )
    else:
        logger.info("Scheduler configured: scan at :00/:15/:30/:45")

    return scheduler

