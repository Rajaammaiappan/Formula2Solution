# Formula2Solution — Website + Callback Backend

Flask app serving the Formula2Solution landing page with a minimal callback
form (name + phone) stored in **Turso (libSQL)**, deployed on **Render**.

## Project structure

```
formula2solution/
├── app.py              # Flask: pages + /api/contact + /health + /api/requests
├── requirements.txt    # Flask, gunicorn, libsql-client
├── render.yaml         # Render blueprint
├── .python-version     # Pins Python 3.12.3 on Render (important!)
└── templates/
    └── index.html      # The full landing page
```

## Deploy in 10 minutes

### 1. Turso (database)
Using the CLI (or do the same in the Turso web dashboard):
```bash
# install: https://docs.turso.tech/cli/installation
turso auth login
turso db create formula2solution --location bom   # bom = Mumbai region
turso db show formula2solution --url              # -> libsql://formula2solution-<org>.turso.io
turso db tokens create formula2solution           # -> your auth token
```
No schema step needed — the app creates the `contact_requests` table
automatically on first boot.

### 2. GitHub
```bash
git init && git add . && git commit -m "Formula2Solution site"
git remote add origin https://github.com/<you>/formula2solution.git
git push -u origin main
```

### 3. Render (hosting)
**Blueprint:** New → Blueprint → select the repo. Render reads `render.yaml`
and asks you to paste the two Turso values.

**Manual:** New → Web Service → repo, then:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --workers 2 --timeout 60`
- Environment variables:

  | Key | Value |
  |---|---|
  | `TURSO_DATABASE_URL` | `libsql://formula2solution-<org>.turso.io` |
  | `TURSO_AUTH_TOKEN` | the token from step 1 |
  | `ADMIN_KEY` | any long random string |
  | `PYTHON_VERSION` | `3.12.3` (or rely on the `.python-version` file) |

### 4. Verify
- `https://<app>.onrender.com/health` → `{"status":"ok","db":"connected"}`
- Submit the callback form, then view rows either in the Turso dashboard
  (Data browser) or via:
  ```bash
  turso db shell formula2solution "SELECT * FROM contact_requests ORDER BY id DESC LIMIT 10"
  ```
- Or over HTTP:
  ```bash
  curl -H "X-Admin-Key: <ADMIN_KEY>" https://<app>.onrender.com/api/requests
  ```

## Run locally
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export TURSO_DATABASE_URL="libsql://formula2solution-<org>.turso.io"
export TURSO_AUTH_TOKEN="<token>"
python app.py   # -> http://localhost:5000
```

## Notes
- **Python version:** pinned to 3.12.3 via `.python-version`. If Render was
  configured before this file existed, add env var `PYTHON_VERSION=3.12.3`
  and use **Manual Deploy → Clear build cache & deploy**.
- **Free-tier sleep:** Render free services sleep when idle; first visit after
  sleep takes ~30–50s.
- **Next steps:** email/WhatsApp notification on each callback request, custom
  domain, and updating placeholder content (team, pricing, case studies).
