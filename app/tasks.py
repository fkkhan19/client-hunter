# app/tasks.py
import os
import time
import logging
from celery import shared_task, Task
from datetime import datetime, timedelta


from app.db import db
from app.models import Lead, Message
from app.sender.email_sender import send_email
from app.sender.whatsapp_sender import send_whatsapp
from app.analyzer.analyzer import analyze_lead

logger = logging.getLogger(__name__)

# Init Flask app for Celery worker
flask_app = create_app()

RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "20"))
RATE_LIMIT_INTERVAL = 60.0 / RATE_LIMIT_PER_MIN
MIN_DAYS_BETWEEN_CONTACT = int(os.getenv("MIN_DAYS_BETWEEN_CONTACT", "14"))
AUTO_SEND_THRESHOLD = int(os.getenv("AUTO_SEND_SCORE_THRESHOLD", "50"))


# TASK BASE CLASS
class FlaskTask(Task):
    _app = flask_app

    def __call__(self, *args, **kwargs):
        with self._app.app_context():
            return self.run(*args, **kwargs)


# ----------------------------------------------------------
# PROCESS A SINGLE LEAD
# ----------------------------------------------------------
@shared_task(bind=True, base=FlaskTask, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_lead(self, lead_data):
    """
    lead_data → dict returned from scraper
    """

    try:
        name = lead_data.get("name") or "Unknown"
        contact = lead_data.get("contact")
        website = lead_data.get("website")
        category = lead_data.get("category")
        location = lead_data.get("location")
        social = lead_data.get("social_links")

        # Validate: don't store leads with nothing
        if not contact and not website:
            logger.info("[SKIP] No contact + no website → %s", name)
            return {"status": "skipped"}

        # --- DUPLICATE CHECK ---
        existing = None
        if website:
            existing = Lead.query.filter_by(website=website).first()
        if not existing and contact:
            existing = Lead.query.filter_by(contact=contact).first()

        # --- UPDATE EXISTING LEAD ---
        if existing:
            existing.name = name
            existing.category = category or existing.category
            existing.location = location or existing.location
            existing.social_links = social or existing.social_links
            db.session.commit()
            lead = existing
        else:
            # CREATE NEW LEAD
            lead = Lead(
                name=name,
                category=category,
                location=location,
                contact=contact,
                website=website,
                social_links=social,
                priority_score=0.0,
                status="new"
            )
            db.session.add(lead)
            db.session.commit()
            logger.info("[NEW LEAD] %s (%s)", lead.id, name)

        # --- ANALYZE ---
        analysis = analyze_lead(lead)
        lead.priority_score = analysis.get("score", 0)
        db.session.commit()

        # --- AUTO SEND DECISION ---
        if lead.priority_score < AUTO_SEND_THRESHOLD:
            return {"status": "low_score"}

        # Check last contact
        last_msg = Message.query.filter_by(lead_id=lead.id).order_by(Message.sent_at.desc()).first()
        if last_msg and (datetime.utcnow() - last_msg.sent_at).days < MIN_DAYS_BETWEEN_CONTACT:
            return {"status": "skip_recent"}

        # Generate message
        from app.message_generator.generator import generate_message
        content = generate_message(lead)

        # Save message as pending
        msg = Message(
            lead_id=lead.id,
            content=content,
            channel="auto",
            status="pending"
        )
        db.session.add(msg)
        db.session.commit()

        time.sleep(RATE_LIMIT_INTERVAL)

        # --- SEND ---
        sent = False
        if contact and "@" in contact:
            send_email(lead, content)
            sent = True
            msg.channel = "email"
        elif contact:
            try:
                send_whatsapp(lead, content)
                sent = True
                msg.channel = "whatsapp"
            except Exception as e:
                logger.warning("[WHATSAPP FAIL] %s", e)

        if sent:
            msg.status = "sent"
            msg.sent_at = datetime.utcnow()
            lead.status = "contacted"
            db.session.commit()
            logger.info("[SENT] Lead %s via %s", lead.id, msg.channel)
            return {"status": "sent"}

        msg.status = "failed"
        db.session.commit()
        return {"status": "failed"}

    except Exception as e:
        logger.exception("process_lead failed: %s", e)
        raise


# ----------------------------------------------------------
# FULL PIPELINE
# ----------------------------------------------------------
@shared_task(bind=True, base=FlaskTask)
def scrape_analyze_send(self, categories=None):
    """
    Full pipeline:
    scrape → normalize → analyze → auto-send
    """

    categories = categories or os.getenv("SCRAPE_CATEGORIES", "mobile repair,electronics repair,salons").split(",")
    city = os.getenv("SCRAPE_CITY", "Pune")
    limit = int(os.getenv("SCRAPE_LIMIT_PER_CATEGORY", "20"))

    logger.info("[PIPELINE] Start for %s", categories)

    try:
        def get_scraper():
    from app.scraper.ultra_scraper import run_category_search
    return run_category_search

    except:
        logger.error("Ultra Scraper missing. Cannot continue.")
        return {"error": "scraper_missing"}

    total = 0

    for cat in categories:
        results = run_category_search(cat.strip(), city, limit)

        for lead_dict in results:
            process_lead.delay(lead_dict)
            total += 1
            time.sleep(RATE_LIMIT_INTERVAL)

    return {"queued": total}
