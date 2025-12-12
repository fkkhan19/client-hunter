# app/models.py

from datetime import datetime
from .db import db


# ============================================================
# LEAD MODEL
# ============================================================
class Lead(db.Model):
    __tablename__ = "lead"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    category = db.Column(db.String(100))
    location = db.Column(db.String(100))
    contact = db.Column(db.String(100))   # phone or email
    website = db.Column(db.String(200))
    social_links = db.Column(db.String(500))
    source = db.Column(db.String(100))
    priority_score = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationship (1 Lead → many Messages)
    messages = db.relationship("Message", backref="lead", lazy="dynamic")

    def __repr__(self):
        return f"<Lead {self.name}>"


# ============================================================
# MESSAGE MODEL
# ============================================================
class Message(db.Model):
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"))
    content = db.Column(db.Text)
    channel = db.Column(db.String(50))         # email / whatsapp / instagram
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="pending")

    def __repr__(self):
        return f"<Message {self.channel} to Lead {self.lead_id}>"


# ============================================================
# USER MODEL (not used yet but okay)
# ============================================================
class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(128))


# ============================================================
# SETTING MODEL (used for scheduler toggle)
# ============================================================
class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True)
    value = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<Setting {self.key}={self.value}>"

    # --------------------------------------
    # Helper: get a boolean config
    # --------------------------------------
    @staticmethod
    def get_bool(key, default=False):
        s = Setting.query.filter_by(key=key).first()
        if not s:
            return default
        return str(s.value).lower() in ("1", "true", "yes", "on")

    # --------------------------------------
    # Helper: set a config
    # --------------------------------------
    @staticmethod
    def set(key, value):
        s = Setting.query.filter_by(key=key).first()
        if not s:
            s = Setting(key=key, value=str(value))
            db.session.add(s)
        else:
            s.value = str(value)
        db.session.commit()
        return s
