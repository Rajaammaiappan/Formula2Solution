-- Run this once in Supabase: SQL Editor > New query > paste > Run
-- (The Flask app also auto-creates it on first boot, but running it
--  yourself lets you verify everything in the dashboard first.)

CREATE TABLE IF NOT EXISTS contact_requests (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ref          TEXT UNIQUE NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    name         TEXT NOT NULL,
    email        TEXT NOT NULL,
    organization TEXT,
    service      TEXT NOT NULL,
    message      TEXT NOT NULL,
    budget       TEXT,
    timeline     TEXT
);

-- Optional: lock the table down so only the connection-string user (postgres)
-- can touch it, since we are NOT using Supabase's client-side API here.
ALTER TABLE contact_requests ENABLE ROW LEVEL SECURITY;
