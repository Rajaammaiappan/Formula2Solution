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

from flask import Flask, render_template, request, jsonify
import libsql_client

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(16))

TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

PHONE_RE = re.compile(r"^\+?[\d\s()\-]{7,17}$")


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
