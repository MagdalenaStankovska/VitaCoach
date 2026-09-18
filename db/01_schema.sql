-- Schema for the `documents` table. This has never been defined in source
-- control before (it was created out-of-band against a manually-provisioned
-- Postgres instance) -- this is the first checked-in definition, written to
-- match exactly what ingest.py/build_index.py/app.py already assume
-- (an `id` primary key and a `content` text column, nothing more).
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL
);
