import time

from app.db.models import Run
from app.db.session import SessionLocal, init_db
from app.services.run_executor import execute_run_by_id


def process_next_run() -> str | None:
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.status == "queued").order_by(Run.queued_at.asc()).first()
        if run is None:
            return None
        run_id = run.id
    finally:
        db.close()
    execute_run_by_id(run_id)
    return run_id


def main() -> None:
    init_db()
    processed = process_next_run()
    if processed is None:
        print("No queued runs.")
    else:
        print(f"Processed queued run {processed}.")


def loop(interval_seconds: int = 10) -> None:
    init_db()
    while True:
        processed = process_next_run()
        if processed is None:
            time.sleep(interval_seconds)


if __name__ == "__main__":
    main()

