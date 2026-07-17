"""
Formula2Solution — Flask app for Render + Turso (libSQL)

Environment variables required (set in Render dashboard):
    TURSO_DATABASE_URL -> from Turso dashboard / CLI, e.g.
                          libsql://formula2solution-yourorg.turso.io
    TURSO_AUTH_TOKEN   -> a database auth token (turso db tokens create <db>)
Optional:
    ADMIN_KEY          -> random string; enables GET /api/requests listing
    SECRET_KEY         -> any random string
"""

import os
import re
import secrets
import smtplib
import threading
import urllib.parse
import urllib.request
from email.message import EmailMessage

from flask import Flask, render_template, request, jsonify
import libsql_client

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(16))

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

PHONE_RE = re.compile(r"^\+?[\d\s()\-]{7,17}$")

# ---------------------------------------------------------------------------
# Notifications (all optional — enabled only when the env vars are set)
#
# Email via Gmail SMTP:
#   SMTP_USER        -> your Gmail address (the sender)
#   SMTP_PASS        -> a Gmail App Password (NOT your normal password)
#   NOTIFY_EMAIL_TO  -> where to receive lead alerts (can be the same address)
#   SMTP_HOST / SMTP_PORT (optional, default smtp.gmail.com:587)
#
# WhatsApp via CallMeBot (free, for personal notifications):
#   CALLMEBOT_PHONE  -> your WhatsApp number with country code, e.g. +9198xxxxxx
#   CALLMEBOT_APIKEY -> key you receive after messaging the CallMeBot number once
# ---------------------------------------------------------------------------

def _send_email(subject: str, body: str):
    user = os.environ.get("SMTP_USER")
    pwd = os.environ.get("SMTP_PASS")
    to = os.environ.get("NOTIFY_EMAIL_TO")
    if not (user and pwd and to):
        return
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)


def _send_whatsapp(text: str):
    phone = os.environ.get("CALLMEBOT_PHONE")
    apikey = os.environ.get("CALLMEBOT_APIKEY")
    if not (phone and apikey):
        return
    url = (
        "https://api.callmebot.com/whatsapp.php?"
        + urllib.parse.urlencode({"phone": phone, "text": text, "apikey": apikey})
    )
    urllib.request.urlopen(url, timeout=20)


def notify_new_lead(ref: str, name: str, phone: str):
    """Fire-and-forget notifications; failures are logged, never user-facing."""
    subject = f"New callback request {ref} — {name}"
    body = (
        f"New lead on formula2solution:\n\n"
        f"Reference: {ref}\nName: {name}\nPhone: {phone}\n\n"
        f"Call them back within one business day."
    )

    def _run():
        try:
            _send_email(subject, body)
        except Exception:
            app.logger.exception("Email notification failed")
        try:
            _send_whatsapp(f"F2S lead {ref}: {name} — {phone}")
        except Exception:
            app.logger.exception("WhatsApp notification failed")

    threading.Thread(target=_run, daemon=True).start()


def _http_url(url: str) -> str:
    """Use stateless HTTPS for one-shot queries (more robust than websockets
    on platforms that sleep/scale workers, like Render's free tier)."""
    if url.startswith("libsql://"):
        return "https://" + url[len("libsql://"):]
    return url


def get_client():
    if not TURSO_URL or not TURSO_TOKEN:
        raise RuntimeError("TURSO_DATABASE_URL / TURSO_AUTH_TOKEN not set")
    return libsql_client.create_client_sync(
        url=_http_url(TURSO_URL), auth_token=TURSO_TOKEN
    )


def init_db():
    with get_client() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS contact_requests (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ref        TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                name       TEXT NOT NULL,
                phone      TEXT NOT NULL
            )
            """
        )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    try:
        with get_client() as c:
            c.execute("SELECT 1")
        return jsonify(status="ok", db="connected"), 200
    except Exception as exc:
        return jsonify(status="degraded", db=str(exc)), 500


@app.route("/api/contact", methods=["POST"])
def contact():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()

    errors = {}
    if not name or len(name) > 120:
        errors["name"] = "Enter your name"
    digits = re.sub(r"\D", "", phone)
    if not PHONE_RE.match(phone) or not (7 <= len(digits) <= 15):
        errors["phone"] = "Enter a valid phone number"

    if errors:
        return jsonify(ok=False, errors=errors), 400

    ref = "F2S-" + secrets.token_hex(3).upper()

    try:
        with get_client() as c:
            c.execute(
                "INSERT INTO contact_requests (ref, name, phone) VALUES (?, ?, ?)",
                [ref, name, phone],
            )
    except Exception:
        app.logger.exception("Failed to store contact request")
        return jsonify(ok=False, error="Could not save your request. Please try again."), 500

    notify_new_lead(ref, name, phone)
    return jsonify(ok=True, ref=ref), 201


@app.route("/api/requests", methods=["GET"])
def list_requests():
    """Recent submissions. Call with header:  X-Admin-Key: <ADMIN_KEY>"""
    admin_key = os.environ.get("ADMIN_KEY")
    if not admin_key or request.headers.get("X-Admin-Key") != admin_key:
        return jsonify(ok=False, error="Unauthorized"), 401
    with get_client() as c:
        rs = c.execute(
            "SELECT ref, created_at, name, phone FROM contact_requests "
            "ORDER BY id DESC LIMIT 100"
        )
        rows = [dict(zip(rs.columns, r)) for r in rs.rows]
    return jsonify(ok=True, count=len(rows), requests=rows)


# Create table on startup (safe: IF NOT EXISTS)
if TURSO_URL and TURSO_TOKEN:
    try:
        init_db()
    except Exception:
        app.logger.exception("init_db failed at startup")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
