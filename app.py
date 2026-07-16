"""
Formula2Solution — Flask app for Render + Supabase (Postgres)

Environment variables required (set in Render dashboard):
    DATABASE_URL  -> Supabase connection string (use the *pooler* URI, port 6543)
                     e.g. postgresql://postgres.xxxx:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
Optional:
    SECRET_KEY    -> any random string (session/security hardening)
"""

import os
import re
import secrets
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(16))

DATABASE_URL = os.environ.get("DATABASE_URL", "")

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

ALLOWED_SERVICES = {
    "Personal career automation (Pit Crew)",
    "Custom software development",
    "Process / task automation",
    "Continuous improvement (CI / Lean)",
    "Data & integration",
    "Website / digital presence",
    "Not sure yet — help me figure it out",
}


def get_conn():
    """Open a new Postgres connection (Supabase pooler handles pooling)."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    """Create the contact_requests table if it doesn't exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS contact_requests (
        id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        ref         TEXT UNIQUE NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        name        TEXT NOT NULL,
        email       TEXT NOT NULL,
        organization TEXT,
        service     TEXT NOT NULL,
        message     TEXT NOT NULL,
        budget      TEXT,
        timeline    TEXT
    );
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    """Render health check. Also verifies DB connectivity."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok", db="connected"), 200
    except Exception as exc:  # pragma: no cover
        return jsonify(status="degraded", db=str(exc)), 500


@app.route("/api/contact", methods=["POST"])
def contact():
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    organization = (data.get("organization") or "").strip() or None
    service = (data.get("service") or "").strip()
    message = (data.get("message") or "").strip()
    budget = (data.get("budget") or "").strip() or None
    timeline = (data.get("timeline") or "").strip() or None

    errors = {}
    if not name or len(name) > 120:
        errors["name"] = "Enter your name"
    if not EMAIL_RE.match(email) or len(email) > 254:
        errors["email"] = "Enter a valid email"
    if service not in ALLOWED_SERVICES:
        errors["service"] = "Pick the closest option"
    if len(message) < 15 or len(message) > 5000:
        errors["message"] = "Tell us a little about the problem"

    if errors:
        return jsonify(ok=False, errors=errors), 400

    ref = "F2S-" + secrets.token_hex(3).upper()

    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contact_requests
                    (ref, name, email, organization, service, message, budget, timeline)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (ref, name, email, organization, service, message, budget, timeline),
            )
    except Exception:
        app.logger.exception("Failed to store contact request")
        return jsonify(ok=False, error="Could not save your request. Please try again."), 500

    return jsonify(ok=True, ref=ref), 201


@app.route("/api/requests", methods=["GET"])
def list_requests():
    """
    Simple protected listing of recent submissions.
    Call with header:  X-Admin-Key: <ADMIN_KEY env var>
    (For anything serious, view rows in the Supabase dashboard instead.)
    """
    admin_key = os.environ.get("ADMIN_KEY")
    if not admin_key or request.headers.get("X-Admin-Key") != admin_key:
        return jsonify(ok=False, error="Unauthorized"), 401
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT ref, created_at, name, email, organization, service, budget, timeline, message "
            "FROM contact_requests ORDER BY created_at DESC LIMIT 100"
        )
        rows = cur.fetchall()
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].astimezone(timezone.utc).isoformat()
    return jsonify(ok=True, count=len(rows), requests=rows)


# Initialize table on startup (safe: CREATE IF NOT EXISTS)
if DATABASE_URL:
    try:
        init_db()
    except Exception:  # don't block boot if DB is briefly unreachable
        app.logger.exception("init_db failed at startup")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
