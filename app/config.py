import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret")

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///client_hunter.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Celery / Redis
    CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

    # Scraper settings
    SCRAPE_CATEGORIES = os.getenv("SCRAPE_CATEGORIES", "mobile repair,electronics repair,salons").split(",")
    SCRAPE_CITY = os.getenv("SCRAPE_CITY", "Pune")
    SCRAPE_LIMIT_PER_CATEGORY = int(os.getenv("SCRAPE_LIMIT_PER_CATEGORY", 30))

    # Auto-send settings
    AUTO_SEND_SCORE_THRESHOLD = int(os.getenv("AUTO_SEND_SCORE_THRESHOLD", 50))
    MIN_DAYS_BETWEEN_CONTACT = int(os.getenv("MIN_DAYS_BETWEEN_CONTACT", 14))
    RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", 20))

    # Email
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    # Twilio
    TWILIO_SID = os.getenv("TWILIO_SID")
    TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
