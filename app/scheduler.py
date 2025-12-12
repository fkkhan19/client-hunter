# -------------------------------------------------------
# FIXED SCHEDULER: Playwright scraper runs in a safe process
# -------------------------------------------------------
import os, sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from datetime import datetime
import multiprocessing
from multiprocessing import Process, Queue

from app.models import Lead, Message
from app.db import db
from app.sender.email_sender import send_email
from app.sender.whatsapp_sender import send_whatsapp
from app.message_generator.generator import generate_message



# ---------- SAFE SCRAPER PROCESS ----------
def scraper_process(category, city, max_results, q):
    try:
        from app.scraper.google_maps_new import get_map_results
        data = get_map_results(category, city, max_results)
        q.put(data)
    except Exception as e:
        print("❌ Scraper crashed:", e)
        q.put([])


# ---------- SCHEDULER ----------
scheduler = BackgroundScheduler(timezone=timezone("Asia/Kolkata"))


def auto_scrape(app):

    with app.app_context():

        print("\n==============================")
        print("🔍 AUTO SCRAPE TRIGGERED (Google Maps)")
        print("==============================\n")

        # LOAD CONFIG
        raw_categories = app.config.get("SCRAPE_CATEGORIES", [])
        if isinstance(raw_categories, str):
            categories = [c.strip() for c in raw_categories.split(",") if c.strip()]
        else:
            categories = raw_categories

        raw_cities = app.config.get("SCRAPE_CITIES_MULTI", [])
        if isinstance(raw_cities, str):
            cities = [c.strip() for c in raw_cities.split(",") if c.strip()]
        else:
            cities = raw_cities

        max_results = int(app.config.get("SCRAPE_LIMIT_PER_CATEGORY", 30))
        threshold = int(app.config.get("AUTO_SEND_SCORE_THRESHOLD", 50))
        min_days = int(app.config.get("MIN_DAYS_BETWEEN_CONTACT", 14))

        total_saved = 0

        # SCRAPE
        for city in cities:
            for cat in categories:

                print(f"➡️ Scraping '{cat}' in '{city}'")

                q = Queue()
                p = Process(target=scraper_process, args=(cat, city, max_results, q))

                p.start()
                p.join(timeout=120)

                if p.is_alive():
                    print("⚠️ Scraper stuck → terminating...")
                    p.terminate()
                    p.join()

                results = q.get() if not q.empty() else []

                if not results:
                    print("   📦 No results returned")
                    continue

                # SAVE RESULTS
                saved_count = 0
                for r in results:
                    name = r.get("name")
                    location = r.get("location") or city
                    contact = r.get("contact")
                    website = r.get("website")
                    score = r.get("score", 0)

                    if not name:
                        continue

                    if Lead.query.filter_by(name=name, location=location).first():
                        continue

                    lead = Lead(
                        name=name,
                        category=cat,
                        location=location,
                        contact=contact,
                        website=website,
                        source="gmaps",
                        priority_score=score,
                        status="new"
                    )

                    db.session.add(lead)
                    saved_count += 1
                    total_saved += 1

                db.session.commit()
                print(f"📦 Saved {saved_count} leads for {cat} → {city}")

        print(f"\n✅ AUTO SCRAPE FINISHED — total_saved={total_saved}\n")

        # AUTO SEND
        print("🔁 Auto-sending messages...")

        now = datetime.utcnow()
        leads = Lead.query.filter(Lead.priority_score >= threshold).all()

        for lead in leads:

            last_msg = Message.query.filter_by(lead_id=lead.id) \
                                    .order_by(Message.sent_at.desc()) \
                                    .first()

            if last_msg:
                days_diff = (now - last_msg.sent_at).days
                if days_diff <= min_days:
                    continue

            msg_text = generate_message(
                lead.name, lead.category, lead.website, lead.priority_score
            )

            sent = False

            if lead.contact and "@" in str(lead.contact):
                sent = send_email(lead.contact, msg_text)
                channel = "email"
            else:
                sent = send_whatsapp(lead.contact, msg_text)
                channel = "whatsapp"

            if sent:
                m = Message(
                    lead_id=lead.id,
                    content=msg_text,
                    channel=channel,
                    status="sent"
                )
                db.session.add(m)
                lead.status = "contacted"
                db.session.commit()

        print("🔚 Auto-send phase finished.\n")



def start_scheduler(app):

    print("🔥 Scheduler starting...")

    if scheduler.get_jobs():
        print("⚠️ Scheduler already running, skipping")
        return scheduler

    interval = int(app.config.get("SCRAPER_INTERVAL_SECONDS", 60))

    scheduler.add_job(
        auto_scrape,
        "interval",
        seconds=interval,
        args=[app]
    )

    scheduler.start()
    print(f"🟢 Scheduler started — every {interval} seconds")

    return scheduler
