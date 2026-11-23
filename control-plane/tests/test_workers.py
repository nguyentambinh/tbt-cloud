# Nguyễn Tâm Bình - 2324801030003
from app.workers.scheduler import create_scheduler


def test_worker_intervals():
    scheduler = create_scheduler()
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert jobs["sync-nodes"].trigger.interval.total_seconds() == 60
    assert jobs["billing"].trigger.interval.total_seconds() == 3600
