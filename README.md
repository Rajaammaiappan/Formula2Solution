# Formula2Solution — Website + Contact Backend

Flask app serving the Formula2Solution landing page with a contact form that
stores enquiries in **Supabase (Postgres)**, deployed on **Render**.

## Project structure

```
formula2solution/
├── app.py                 # Flask app: pages + /api/contact + /health
├── requirements.txt       # Flask, gunicorn, psycopg2-binary
├── render.yaml            # Render blueprint (one-click deploy config)
├── supabase_schema.sql    # DB table (also auto-created by the app)
└── templates/
    └── index.html         # The full landing page
```

## Deploy in 10 minutes

### 1. Supabase (database)
1. Create a free project at supabase.com (pick a region near your Render region,
   e.g. `ap-south-1` Mumbai if deploying Render in Singapore/Oregon isn't critical).
2. Open **SQL Editor → New query**, paste `supabase_schema.sql`, click **Run**.
3. Go to **Project Settings → Database → Connection string → URI**, and choose the
   **Transaction pooler** variant (port **6543**). Copy it and replace `[YOUR-PASSWORD]`
   with your database password. It looks like:
   ```
   postgresql://postgres.abcdefgh:YOURPASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
   ```
   > Use the pooler (6543), not the direct connection (5432) — Render's free tier
   > spins workers up/down and the pooler handles that gracefully.

### 2. GitHub
Push this folder to a new GitHub repo:
```bash
git init && git add . && git commit -m "Formula2Solution site"
git remote add origin https://github.com/<you>/formula2solution.git
git push -u origin main
```

### 3. Render (hosting)
**Option A — Blueprint (easiest):** New → Blueprint → select the repo.
Render reads `render.yaml`, then asks you to paste `DATABASE_URL`. Done.

**Option B — Manual:** New → Web Service → select repo, then set:
- Runtime: **Python 3**
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --workers 2 --timeout 60`
- Environment variables:
  | Key | Value |
  |---|---|
  | `DATABASE_URL` | your Supabase pooler URI |
  | `SECRET_KEY` | any long random string |
  | `ADMIN_KEY` | any long random string (for /api/requests) |

### 4. Verify
- Open `https://<your-app>.onrender.com/health` → should show `{"status":"ok","db":"connected"}`
- Submit the contact form → check **Supabase → Table Editor → contact_requests**
- Optional API check of recent submissions:
  ```bash
  curl -H "X-Admin-Key: <ADMIN_KEY>" https://<your-app>.onrender.com/api/requests
  ```

## Run locally

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://...supabase...:6543/postgres"   # Windows: set DATABASE_URL=...
python app.py
# → http://localhost:5000
```

## Notes & next steps
- **Python version (important):** Render defaults to the newest Python (3.14),
  which breaks `psycopg2-binary`. This repo pins **3.12.3** via the
  `.python-version` file. If you configured the service manually before this
  file existed, either redeploy after pushing it, or add an env var
  `PYTHON_VERSION=3.12.3` in Render → Environment. Then use
  **Manual Deploy → Clear build cache & deploy**.
- **Free-tier sleep:** Render free web services sleep after inactivity; the first
  visit after sleep takes ~30–50s. Upgrade to Starter to remove this.
- **Custom domain:** Render → Settings → Custom Domains (add formula2solution.com,
  point DNS as instructed, free TLS included).
- **Email notifications:** easy to add — a few lines in `/api/contact` using
  Resend/Brevo/SMTP so every enquiry also lands in your inbox.
- **Switching to Turso later:** only `get_conn()` / SQL in `app.py` would change
  (swap `psycopg2` for `libsql-client`); the frontend and routes stay identical.
- Placeholders to update before launch: team names, pricing, case studies,
  email address, LinkedIn links.
