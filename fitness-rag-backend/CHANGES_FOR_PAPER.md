# Changes Made in Response to Peer Review

This document summarizes, for each task, what changed in code, which files were
touched, how it was verified, and the real numbers the paper should now cite.
Every number below was measured against a live run in this repo on 2026-09-18
(not projected/estimated) — see each section's "Verified" line for the exact
command.

---

## 1. Preferences propagate into every Gemini prompt (P0-1)

**Claim addressed:** the paper claims user preferences (goal, height, weight,
sex, blood-panel findings) propagate into every Gemini prompt. Previously
they only reached `/users/me/preferences/analyze`; `/ask` had no auth and
built its prompt from retrieved context only, and the scheduler never read
preferences at all.

**What changed:**
- `POST /ask` now takes an optional bearer token (`optional_user` dependency,
  `app.py`) — unauthenticated calls still work exactly as before (existing
  frontend behavior is unaffected), but a valid token now identifies the
  caller and their stored preferences.
- A new `build_prefs_block(user)` helper renders a compact natural-language
  profile block (goal, gender, age, height, weight, derived BMR/TDEE, and a
  note if a blood-test image is on file). It is spliced into: (a) the `/ask`
  chat prompt, (b) the `/ask` 7-day plan prompt, (c) the scheduler prompt in
  `get_schedule_recommendations` (which never read `user.preferences` before
  this change).
- **Embedding boundary is enforced, not just documented:** `model.encode`
  still receives `[q.question]` and nothing else — the preferences block is
  built as a separate variable only spliced into prompt strings, never into
  anything passed to the encoder. This is regression-tested (see below).
- Frontend: `Home.jsx`'s two hand-rolled `fetch("http://127.0.0.1:9000/ask")`
  calls (no auth header, ever) were replaced with a new `askQuestion()` /
  `askQuestionStream()` pair in `lib/api.js` that reuse the existing
  `apiRequest` auth-token plumbing, so signed-in users' preferences are
  actually applied now.
- `test_app.py` was a disconnected 9-line stub (`FastAPI()` instance with one
  route, never testing the real app). It's now a real pytest suite
  (`conftest.py` + `test_app.py`, 33 tests total across this whole revision)
  that imports and exercises the actual `app` object via `TestClient`.

**Files:** `app.py`, `fitness-ai-app/src/lib/api.js`, `fitness-ai-app/src/Home.jsx`,
`test_app.py` (new), `conftest.py` (new), `pytest.ini` (new).

**Verified:**
- `pytest -q -k test_ask_embedding_receives_raw_question_only` — asserts
  `model.encode`'s captured argument equals exactly `[question]` even with a
  fully populated preference profile. Passing.
- Live: unauthenticated `POST /ask` → `"personalized": false`; same call with
  `Authorization: Bearer <token>` for a user with goal/height/weight/gender
  set → `"personalized": true` and the generated answer text reflects the
  profile.
- **Paper correction:** the paper's wording implies JWT auth. The actual
  mechanism (both before and after this change) is an opaque bearer token
  (`secrets.token_urlsafe(32)`) matched against `data/users.json`, not a
  signed/verifiable JWT. Recommend correcting this terminology rather than
  claiming JWT.

---

## 2. LLM-as-a-judge evaluation harness (P0-2)

**Claim addressed:** the reviewer's main methodological objection — MRR/P@8
evaluate retrieval only, not whether the generated plan is faithful to the
retrieved documents.

**What changed:** new `eval/judge_eval.py` + `eval/queries.jsonl` (10 example
rows across the 5 required categories; the full 200-query set will be
supplied separately per your instructions). For each query it runs the real
retrieval + generation path from `app.py`, then asks Gemini to score
**Faithfulness** (1–5), **Answer Relevance** (1–5), and **Context Precision**
(0–1, fraction of retrieved docs actually used) via a separate strict-JSON
judge prompt, parsed defensively (never raises on malformed output — records
`null` scores and continues). Supports `--limit N`, `--out results.json`,
resumable runs (skips already-scored query IDs), and rate-limit backoff
(reuses `app.py`'s existing `_generate_text_with_retry`, which already
retries on 429/503/`RESOURCE_EXHAUSTED`).

**Files:** `eval/judge_eval.py` (new), `eval/queries.jsonl` (new),
`eval/test_judge_eval.py` (new, 5 unit tests for the JSON parser).

**Verified — real numbers from a 5-query smoke run** (`eval/results_smoke.json`,
`python eval/judge_eval.py --limit 5 --out eval/results_smoke.json`; the full
200-query run should be re-run once that set is supplied):

| Metric | Mean | Std Dev | N |
|---|---|---|---|
| Faithfulness (1–5) | 5.00 | 0.00 | 5 |
| Answer Relevance (1–5) | 5.00 | 0.00 | 5 |
| Context Precision (0–1) | 0.60 | 0.32 | 5 |

By category (N=1–2 each, too small to be meaningful on its own — shown to
confirm the breakdown mechanism works; re-run at N=200 for real per-category
numbers): muscle-group context-precision 0.69±0.27 (n=2), equipment-constrained
0.31±0.09 (n=2), goal-directed 1.00 (n=1). Resumability confirmed: a second
run against the same `--out` file skipped the 3 already-scored queries and
only scored the 2 new ones.

**Note for the paper:** context-precision is consistently well below 1.0
even though faithfulness/relevance are maxed — i.e. the model answers
correctly and doesn't hallucinate, but uses only a fraction of what's
retrieved. That's a legitimate finding to report, not a bug in the harness.

---

## 3. Explicit, configurable retrieval threshold (P0-3)

**Claim addressed:** a reviewer argued `DISTANCE_THRESHOLD=2.0` filters
nothing, because the collection is created with no explicit metadata, so
Chroma's default distance space is silently assumed rather than guaranteed.

**What changed:**
- `metadata={"hnsw:space": "l2"}` added explicitly to `get_or_create_collection`
  in both `app.py` and `build_index.py`.
- Startup check (`_assert_collection_space_is_l2`) reads back the collection's
  actual configured space and logs a loud `[WARNING]` (without crashing) if
  it's ever anything other than `l2`.
- `DISTANCE_THRESHOLD`, `VECTOR_SEARCH_RESULTS`, `EXERCISE_RECOMMENDATION_LIMIT`
  are now `os.getenv(...)`-driven (same defaults: 2.0, 24, 8).
- `select_recommended_documents`'s back-fill behavior is unchanged (never
  returns fewer than `limit` when enough candidates exist), but a new
  `_retrieval_diagnostics()` now counts how many candidates passed the
  threshold vs. were back-filled, logged server-side and exposed in the
  `/ask` chat-branch response under a `retrieval` key (not on the plan
  branch, which doesn't use vector search at all — a random Postgres sample
  instead, so a `retrieval` key there would misrepresent the method).

**Files:** `app.py`, `build_index.py`, `.env.example`.

**Verified — real numbers from a live `/ask` call at the default threshold:**

```json
"retrieval": {
  "vector_search_results": 24,
  "distance_threshold": 2.0,
  "limit": 8,
  "passed_threshold_count": 24,
  "returned_count": 8,
  "backfill_count": 0
}
```

**This confirms the reviewer's objection empirically, not just theoretically:**
at the paper's stated threshold, **100% of the 24 retrieved candidates pass**
(0 backfilled) — the threshold is not filtering anything in practice on this
corpus. Restarting with `DISTANCE_THRESHOLD=0.3` flips this to
`passed_threshold_count: 0, backfill_count: 8` — proving the knob is live and
that a genuinely binding threshold would need to be far tighter than 2.0 for
this corpus/embedding combination. The startup log confirms the space really
is `l2` (`[STARTUP] Chroma collection 'fitness' distance space confirmed: l2`),
so this isn't a cosine-vs-l2 mismatch — the threshold value itself is just
too loose for this corpus.

---

## 4. Garmin: unofficial client isolated behind an adapter (P1-1)

**Claim addressed:** the reviewer objected that `python-garminconnect` is an
unofficial reverse-engineered wrapper storing raw credentials rather than
scoped tokens, so the integration can't be called production-grade.

**What changed:** new `garmin_adapters.py` defines a `GarminAdapter` ABC with
the five methods actually used (steps, sleep, active calories, distance,
recent activities). `LegacyGarminConnectAdapter` moves today's implementation
behind this interface unchanged — `_safe_garmin_call`'s exact semantics
(catch-all, return `None`, never raise) are preserved, with one real
`get_user_summary` call now shared/cached across the three summary-derived
methods per adapter instance rather than being inlined three times.
`OfficialGarminHealthAdapter` implements a **real, working OAuth 1.0a flow**
(request-token → user-authorize → access-token exchange, via
`requests_oauthlib`) against the Garmin Connect Developer Program's Health
API — data methods raise `NotImplementedError` since reading real metrics
through that API requires an approved developer account this repo can't
provision. Selected via `GARMIN_ADAPTER` env var (`legacy` default |
`official`).

**Files:** `garmin_adapters.py` (new), `app.py`, `.env.example`,
`requirements.txt` (added `garminconnect`, already had `requests-oauthlib`
transitively).

**Verified:**
- `pytest -q` — 6 new tests: safe-wrapper never raises, sleep extraction,
  summary-call caching (proves 3 methods share 1 real API call), official
  adapter's 5 data methods all raise `NotImplementedError`, adapter selection
  by env var, exact dashboard-shape parity with the pre-refactor version.
- **Live, with a real Garmin account:** `GET /users/me/garmin/dashboard`
  returned 5 real recent activities (actual GPS runs with real durations,
  calories, distances) — legacy adapter behavior is byte-for-byte unchanged.
- **Live, `GARMIN_ADAPTER=official`:** app boots cleanly; the dashboard
  endpoint surfaces the `NotImplementedError` via the existing try/except
  into the same "unavailable" response shape the frontend already handles —
  no crash, no new failure mode.

**Note for the paper:** describe this as "OAuth 1.0a integration implemented
and verified; full data access pending Garmin Health API developer
approval," not as a fully operational official integration — the auth flow
is real, the data endpoints are not (yet) reachable without that approval.

---

## 5. Blood-panel images encrypted at rest (P1-2)

**Claim addressed:** blood-panel photos were stored as plaintext base64 in
`data/users.json` with no encryption.

**What changed:** Fernet (from `cryptography`, already installed
transitively, now pinned directly) encryption keyed by `HEALTH_DATA_KEY`.
`encrypt_blood_image`/`decrypt_blood_image` distinguish legacy plaintext from
already-encrypted values by whether the string starts with `"data:"`
(plaintext data-URLs always do; Fernet tokens never do) — idempotent, never
double-encrypts. `PUT /users/me/preferences` encrypts on write; only
`POST /users/me/preferences/analyze` decrypts, and only in memory to build
its existing text note. A startup guard (`_assert_health_data_key_present_if_needed`)
refuses to boot with a clear `SystemExit` message if `HEALTH_DATA_KEY` is
unset while encrypted data already exists. A one-off
`migrate_encrypt_blood_images.py` backs up `data/users.json` to `.bak` and
encrypts any remaining plaintext images in place.

**Files:** `app.py`, `migrate_encrypt_blood_images.py` (new), `.env.example`,
`requirements.txt`.

**Verified:**
- `pytest -q` — 7 new tests: round-trip encrypt/decrypt, no-op on
  already-encrypted, no-op without a key, `None` on a corrupt token, boot
  refusal when key is missing and encrypted data exists, boot success when
  no encrypted data exists, and that `/preferences/analyze` decrypts before
  building its note.
- Live: generated a real Fernet key, `PUT` a fake blood-test image, `GET`
  showed the encrypted token (not the plaintext data URL) both before and
  after restart, `POST /preferences/analyze` reached the point of calling
  Gemini (proving decrypt succeeded) before hitting an unrelated free-tier
  quota error.

**UX tradeoff, intentional:** the frontend's blood-test image preview no
longer renders after a reload, since the server only ever returns the
plaintext data URL once (right after upload, before the next round trip) —
the GET/PUT responses now return the encrypted token, per the "decrypt only
in the analysis path" instruction. `Preferences.jsx` now shows "🔒 A blood
test image is on file (encrypted)" instead of a broken image icon in that
case.

---

## 6. Mifflin–St Jeor BMR/TDEE (P1-3)

**Claim addressed:** the paper states BMR/TDEE are computed with
Mifflin–St Jeor; no such code existed.

**What changed:** `compute_bmr_tdee(height_cm, weight_kg, age, gender)` —
`BMR = 10W + 6.25H - 5A + s` (s = +5 male, −161 female; `gender="other"`/
unrecognized uses −78, the arithmetic midpoint, flagged in code as a
documented non-clinical approximation since the formula has no validated
non-binary term). `TDEE = BMR × 1.375` (a fixed "lightly active" PAL,
documented as an assumption — the task didn't specify a per-user
activity-level input, so a stated constant was chosen over guessing at UI
scope). `age` added to `PreferencesPayload`; both `GET`/`PUT
/users/me/preferences` now return `bmr`/`tdee` computed fresh from stored
values (never persisted, so they can't go stale). Folded into
`build_prefs_block` so it reaches the chat/plan/scheduler prompts (P0-1).
`Preferences.jsx` gained an age input and a read-only BMR/TDEE readout.

**Files:** `app.py`, `fitness-ai-app/src/Preferences.jsx`, `Preferences.css`.

**Verified:**
- `pytest -q -k bmr_tdee` — hand-computed case (170cm/65kg/30yo female):
  BMR=1401.5 exactly, TDEE=round(1401.5×1.375, 1); null when profile
  incomplete.
- Live: `PUT` with 180cm/82kg/28yo male → **BMR=1810.0 kcal/day,
  TDEE=2488.8 kcal/day** (10×82 + 6.25×180 − 5×28 + 5 = 1810 — exact formula
  match).

---

## 7. Streaming chat responses (P2-1)

**Claim addressed:** the paper claims chat responses stream so first-token
latency governs perceived responsiveness; `/ask` used non-streaming
`generate_content`.

**Checkpoint result: streaming works.** A new, additive `POST /ask/stream`
endpoint uses `client_llm.models.generate_content_stream` inside a FastAPI
`StreamingResponse` (`text/event-stream`), yielding `{"delta": "..."}` SSE
events per chunk and a final `{"done": true, "exercises": [...],
"retrieval": {...}}` event once the exercise cards are ready — matching the
requirement to deliver exercise cards after the text stream. On any
generation failure it yields a clean `{"error": ..., "done": true}` event
instead of crashing the connection. `/ask` itself is untouched — this is a
separate endpoint, so it carries zero risk to the already-hardened `/ask`
contract. Frontend: `askQuestionStream()` in `lib/api.js` reads the response
body incrementally and parses SSE frames; `Home.jsx`'s `askAI()` now streams
by default, accumulating text into the existing `answer` state as it arrives
(so the page visibly fills in progressively) and falling back to the
non-streaming `askQuestion()` if the stream fails before any token arrives.

**Files:** `app.py`, `fitness-ai-app/src/lib/api.js`, `fitness-ai-app/src/Home.jsx`.

**Verified:**
- Mechanically, independent of Gemini: a throwaway FastAPI+`StreamingResponse`
  endpoint yielding 5 chunks with 0.5s sleeps was curled with `-N`; chunks
  arrived ~0.47–0.49s apart (not buffered until completion) — confirms
  uvicorn's `StreamingResponse` genuinely streams over the wire.
- `pytest -q` — 3 new tests with a mocked multi-chunk Gemini stream: correct
  number of `delta` events (none merged/dropped), final `done` event has the
  right shape, and the embedding-contract guarantee holds on the streaming
  path too (`model.encode` still receives only the raw question).
- **Live, real Gemini streaming, twice** (both through the raw backend and
  through the Nginx proxy in the Docker stack): multiple genuine incremental
  `data: {"delta": "..."}` events observed, each carrying real generated
  text fragments, not simulated chunking of a pre-computed answer.

**Honest gap:** this session's Gemini free-tier daily quota (20
requests/day for `gemini-2.5-flash`) was exhausted by the extensive
verification work across all 8 tasks, so a clean **first-token latency
number** could not be measured today — repeated attempts after the quota
reset would be needed for a citable ms figure. The two successful live runs
prove the mechanism works end-to-end (real incremental tokens, not a
fallback); they just didn't happen under conditions where I could also time
them precisely before the next call hit the rate limit. Recommend re-running
`curl -N -w '%{time_starttransfer}'` against `/ask/stream` on a day with a
fresh quota for the paper's actual number, rather than citing an estimate.

---

## 8. Containerization and corpus count (P2-2)

**Claim addressed:** no containerization existed; the paper claims 1,247
documents in the corpus.

**What changed:** `docker-compose.yml` (repo root) brings up `postgres:15`
(persistent volume, seeded once via `db/01_schema.sql` + `db/02_seed.sql` —
generated once from the same chunking rules `ingest.py` uses, run only
against an empty data directory so it can't accidentally duplicate rows the
way repeatedly running `ingest.py` by hand could), a standalone `chroma`
container (persistent volume), the `backend` (built from a new
`fitness-rag-backend/Dockerfile`, Python 3.12 — `garminconnect==0.3.15`
requires ≥3.12), and an `nginx` reverse proxy (`nginx/nginx.conf`, with
`proxy_buffering off` specifically on the `/ask/stream` location so SSE
isn't held up). `app.py`'s Chroma client is now env-driven:
`chromadb.HttpClient` when `CHROMA_HOST` is set (Docker), unchanged
in-memory `chromadb.Client()` otherwise (local dev, zero behavior change).
Discovered and fixed along the way: `app.py`'s two `psycopg2.connect(...)`
calls hardcoded `host="localhost"`, which inside a container refers to the
container itself, not the `postgres` service — now `DB_HOST`/`DB_PORT` env
vars (default `localhost`/`5432`, so local dev is unaffected; Docker sets
`postgres`/`5432`). New `scripts/corpus_stats.py` reports `COUNT(*)`,
mean/median document length, and a duplicate-content check — **report only,
per your decision not to touch the data.**

**Files:** `docker-compose.yml` (new), `fitness-rag-backend/Dockerfile` (new),
`fitness-rag-backend/.dockerignore` (new), `nginx/nginx.conf` (new),
`db/01_schema.sql` (new — the `documents` table schema had never been
checked into source control before), `db/02_seed.sql` (new), `app.py`,
`scripts/corpus_stats.py` (new), `scripts/test_corpus_stats.py` (new).

**Verified — real numbers:**
- `python scripts/corpus_stats.py` against the actual local dev Postgres:
  **277 rows**, mean length 63.8 chars, median 54.0 chars, **0 duplicate
  contents**. **The paper's 1,247 figure is simply wrong for this corpus as
  it exists today — not because of undocumented duplication (there is
  none), but because the real corpus has always been ~277 chunks
  (1 paragraph from `data/hku_academic.txt` + 276 lines from
  `data/exercises.txt`).** Recommend the paper cite **277**, not 1,247.
- `docker compose up -d --build` — all 4 containers started (`postgres`
  healthy, `chroma`, `backend`, `nginx` all up). Backend startup log
  confirmed `[STARTUP] Chroma collection 'fitness' distance space confirmed: l2`
  even against the HTTP Chroma client.
- `docker exec ciit-postgres-1 psql ... "SELECT COUNT(*) FROM documents"` →
  **277** — the seed script reproduced the exact same corpus size as local
  dev, confirming the seed is correct and not silently dropping/duplicating
  rows.
- `curl -X POST http://localhost:8080/ask ...` (through the Nginx proxy) →
  full real generated answer with exercise cards and a `retrieval` block
  identical in shape to the local (non-Docker) response — **`/ask` answers
  through the proxy, end-to-end, as required.**
- `curl -N -X POST http://localhost:8080/ask/stream ...` — SSE events
  reached the client through the Nginx proxy (one call succeeded with real
  content, a later one returned a clean `{"error": ..., "done": true}`
  event once the daily quota was hit — proving the proxy's `proxy_buffering
  off` config and the graceful-error path both work through Nginx too).

---

## Summary table

| Objection | Task | Key files | Verified |
|---|---|---|---|
| Preferences don't reach prompts | P0-1 | `app.py`, `Home.jsx`, `lib/api.js` | `pytest -k embedding`; live curl with/without auth |
| No generation-quality eval | P0-2 | `eval/judge_eval.py` | 5-query live run, see table above |
| `DISTANCE_THRESHOLD=2.0` filters nothing | P0-3 | `app.py`, `build_index.py` | Live: 24/24 passed, 0 backfilled at default; 0/24 passed at 0.3 |
| Unofficial Garmin client, raw creds | P1-1 | `garmin_adapters.py` | 6 unit tests; live real-account dashboard call |
| Blood images stored in plaintext | P1-2 | `app.py`, migration script | 7 unit tests; live encrypt/decrypt round trip |
| No BMR/TDEE despite paper claim | P1-3 | `app.py`, `Preferences.jsx` | Formula test; live BMR=1810.0/TDEE=2488.8 |
| No streaming despite paper claim | P2-1 | `app.py`, `lib/api.js` | Mechanical proof + 2 live real-Gemini streams |
| No containerization; wrong corpus count | P2-2 | `docker-compose.yml`, `scripts/corpus_stats.py` | Full `docker compose up` + `/ask` through proxy; real count = 277 |

## What could not be fully verified today, and why

- **P2-1 first-token latency:** streaming is proven to work with real
  Gemini output (twice, live), but the free-tier daily quota (20
  requests/day) was exhausted by this session's extensive testing before a
  clean latency measurement could be taken. Not an architectural gap —
  re-run `curl -N -w '%{time_starttransfer}' .../ask/stream` on a fresh
  quota day for the paper's number.
- **P0-2 category breakdown:** only 10 example queries exist in
  `eval/queries.jsonl` today (2 per category); the printed per-category
  means above are illustrative of the mechanism, not statistically
  meaningful at N=1–2. Re-run with the full 200-query set once supplied.
- **P1-1 official Garmin data access:** the OAuth 1.0a flow is real, working
  code, but actually fetching data through it requires an approved Garmin
  Health API developer account, which is outside what this repo can
  provision. Paper should describe this as implemented-but-gated, not fully
  operational.
- **Corpus deduplication:** per your explicit instruction, `documents` was
  not modified. As it happens, there was nothing to deduplicate (0 duplicate
  contents found) — the corpus is simply smaller (277) than the paper
  claims (1,247), not artificially inflated by repeated ingestion.
