# app/dashboard/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from app.models import Lead, Message
from app.db import db
from datetime import datetime, timedelta
from app.message_generator.generator import generate_message
from app.sender.email_sender import send_email
from app.sender.whatsapp_sender import send_whatsapp

dashboard = Blueprint(
    "dashboard",
    __name__,
    template_folder="templates",
    static_folder="static"
)

PER_PAGE = 15

def apply_date_query(range_key):
    if not range_key:
        return Lead.query
    today = datetime.utcnow().date()
    if range_key == "today":
        return Lead.query.filter(Lead.created_at >= today)
    if range_key == "yesterday":
        start = today - timedelta(days=1)
        end = start + timedelta(days=1)
        return Lead.query.filter(Lead.created_at >= start, Lead.created_at < end)
    if range_key == "7":
        start = datetime.utcnow() - timedelta(days=7)
        return Lead.query.filter(Lead.created_at >= start)
    if range_key == "30":
        start = datetime.utcnow() - timedelta(days=30)
        return Lead.query.filter(Lead.created_at >= start)
    return Lead.query

@dashboard.route("/")
def home():
    page = request.args.get("page", 1, type=int)
    range_key = request.args.get("range")
    query = apply_date_query(range_key)
    pagination = query.order_by(Lead.priority_score.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    leads = pagination.items

    total_leads = Lead.query.count()
    new_leads = Lead.query.filter(Lead.created_at >= datetime.utcnow() - timedelta(days=1)).count()
    messages_sent = Message.query.filter_by(status="sent").count()

    return render_template(
        "dashboard.html",
        leads=leads,
        pagination=pagination,
        total_leads=total_leads,
        new_leads=new_leads,
        messages_sent=messages_sent,
        range_key=range_key
    )

# send message route
@dashboard.route("/send_message", methods=["POST"])
def send_message():
    lead_id = request.form.get("lead_id") or request.json.get("lead_id")
    channel = request.form.get("channel") or request.json.get("channel")
    content = request.form.get("message") or request.json.get("message")

    if not lead_id:
        return "Missing lead id", 400

    lead = Lead.query.get(lead_id)
    if not lead:
        return "Lead not found", 404

    # if content is empty, generate
    if not content:
        content = generate_message(lead)

    message = Message(lead_id=lead.id, content=content, channel=channel, status="pending")
    db.session.add(message)
    db.session.commit()

    # attempt send based on channel
    try:
        if channel == "email":
            send_email(lead, content)  # send_email should handle logging or raise
        elif channel == "whatsapp":
            send_whatsapp(lead, content)
        else:
            # unknown channel: mark pending
            pass

        message.status = "sent"
        db.session.commit()
        return redirect(request.referrer or url_for("dashboard.home"))
    except Exception as e:
        # mark failed and return error
        message.status = "failed"
        db.session.commit()
        return f"Send failed: {e}", 500


# delete one lead
@dashboard.route("/delete_lead/<int:lead_id>")
def delete_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    return redirect(request.referrer or url_for("dashboard.home"))


# delete multiple (supports form POST or JSON)
@dashboard.route("/delete_multiple", methods=["POST"])
def delete_multiple():
    # Accept both form and JSON
    ids = request.form.getlist("lead_ids")
    if not ids:
        try:
            payload = request.get_json(force=True, silent=True) or {}
            ids = payload.get("ids") or payload.get("lead_ids") or []
        except Exception:
            ids = []

    if not ids:
        return redirect(request.referrer or url_for("dashboard.home"))

    # convert to ints
    ids = [int(x) for x in ids]
    Lead.query.filter(Lead.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    # if JSON request, return JSON
    if request.is_json:
        return jsonify({"deleted": ids})
    return redirect(request.referrer or url_for("dashboard.home"))


# messages page
@dashboard.route("/messages")
def messages_page():
    # show all messages, newest first
    messages = Message.query.order_by(Message.sent_at.desc()).all()
    # template expects "messages" or "msgs" depending on your HTML - we'll supply "messages"
    return render_template("messages.html", messages=messages)


# stats page (chart data)
@dashboard.route("/stats")
def stats_page():
    total_leads = Lead.query.count()
    messages_sent = Message.query.filter_by(status="sent").count()

    # For charts: build arrays of last 14 days counts
    days = 14
    labels = []
    lead_counts = []
    message_counts = []
    for i in range(days-1, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        labels.append(day.strftime("%Y-%m-%d"))
        lead_counts.append(Lead.query.filter(Lead.created_at >= day, Lead.created_at < day + timedelta(days=1)).count())
        message_counts.append(Message.query.filter(Message.sent_at >= day, Message.sent_at < day + timedelta(days=1), Message.status=="sent").count())

    return render_template("stats.html",
                           total_leads=total_leads,
                           messages_sent=messages_sent,
                           lead_dates=labels,
                           lead_counts=lead_counts,
                           msg_counts=message_counts)
