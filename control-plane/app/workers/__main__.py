# Nguyễn Tâm Bình - 2324801030003
from threading import Event

from app.workers.scheduler import create_scheduler
from app.services import notify


def main():
    notify.start_sender()
    scheduler = create_scheduler()
    scheduler.start()
    try:
        Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.shutdown(wait=True)
        notify.stop_sender()


if __name__ == "__main__":
    main()
