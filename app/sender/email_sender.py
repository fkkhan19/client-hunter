# app/sender/email_sender.py
import os
import smtplib
from email.mime.text import MIMEText
from app.db import db
from app.models import Message
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = EMAIL_ADDRESS or "no-reply@example.com"

def _is_email(addr):
    if not addr:
        return False
    return "@" in addr and "." in addr

def send_email(lead, content):
    """
    Sends email to lead. If lead.contact looks like an email, use it.
    If SMTP creds are missing, this function will act as MOCK (logs to console).
    """
    recipient = lead.contact if _is_email(lead.contact) else None

    # If no recipient, try a 'website contact' setting (future), else bail
    if not recipient:
        # For now we treat contact as missing and raise so we mark message failed
        raise ValueError("Lead has no email address in contact field")

    msg = MIMEText(content, "plain", "utf-8")
    msg["From"] = EMAIL_FROM
    msg["To"] = recipient
    msg["Subject"] = f"Business Opportunity for {lead.name}"

    # If SMTP creds not set, do a mock send (print only)
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("[MOCK EMAIL] To:", recipient)
        print("[MOCK EMAIL] Subject:", msg["Subject"])
        print("[MOCK EMAIL] Body:", content[:400])
        return True

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.sendmail(EMAIL_FROM, [recipient], msg.as_string())
        print("[EMAIL SENT]", recipient)
        return True
    except Exception as e:
        print("[EMAIL ERROR]", e)
        raise
