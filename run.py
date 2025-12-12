import multiprocessing
from app import create_app
from app.scheduler import start_scheduler

if __name__ == "__main__":
    multiprocessing.freeze_support()

    app = create_app()

    # START SCHEDULER ONLY HERE
    start_scheduler(app)

    # CRITICAL: DISABLE RELOADER FOR MULTIPROCESS SCRAPER
    app.run(host="0.0.0.0", port=5000, use_reloader=False)
