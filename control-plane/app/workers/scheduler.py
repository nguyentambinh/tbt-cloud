# Nguyễn Tâm Bình - 2324801030003
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import get_session_factory
from app.services.billing import bill_instances
from app.services.node_sync import sync_nodes
from app.services.payos import poll_payments

logger = logging.getLogger(__name__)


def run_job(service):
    try:
        with get_session_factory()() as db:
            service(db)
    except Exception:
        logger.error("Tác vụ nền chưa hoàn tất: %s", service.__name__)


def create_scheduler():
    scheduler = BackgroundScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300})
    scheduler.add_job(run_job, "interval", seconds=60, args=[sync_nodes], id="sync-nodes")
    scheduler.add_job(run_job, "interval", hours=1, args=[bill_instances], id="billing")
    scheduler.add_job(run_job, "interval", seconds=60, args=[poll_payments], id="payos")
    return scheduler
