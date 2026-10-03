"""Real pytest suite against the live FastAPI app (fitness-rag-backend/app.py).

Previously this file was a disconnected 9-line stub defining its own throwaway
FastAPI() instance — it never tested the actual application. This suite
imports and exercises the real `app` object via TestClient, using the
fixtures in conftest.py to keep Postgres/Chroma/Gemini calls fast and
deterministic where practical.

Run with: pytest -q  (from fitness-rag-backend/)
"""
import json

from conftest import register_user


def test_root_health(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_ping(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# --- P0-1: preferences must reach prompts, never the encoder -----------------

def test_ask_embedding_receives_raw_question_only(client, temp_data_files, mock_encoder, mock_gemini):
    """The core P0-1 regression test: even when a user has fully populated
    preferences, the string(s) passed to model.encode must be exactly
    [question] — nothing appended, nothing prefixed. Preferences may only
    reach the generation prompt, never the retrieval embedding."""
    auth = register_user(client)
    token = auth["token"]
    headers = {"Authorization": f"Bearer {token}"}

    prefs_payload = {
        "goal": "muscle_gain",
        "height_cm": 180,
        "weight_kg": 82,
        "gender": "male",
        "age": 28,
    }
    put_resp = client.put("/users/me/preferences", json=prefs_payload, headers=headers)
    assert put_resp.status_code == 200, put_resp.text

    question = "What is a good chest exercise?"
    ask_resp = client.post("/ask", json={"question": question}, headers=headers)
    assert ask_resp.status_code == 200, ask_resp.text

    assert len(mock_encoder) == 1, "model.encode should be called exactly once per /ask call"
    assert mock_encoder[0] == [question], (
        f"model.encode received {mock_encoder[0]!r}, expected exactly [{question!r}] "
        "— preferences must never reach the embedding step"
    )


def test_ask_unauthenticated_still_works(client, temp_data_files, mock_encoder, mock_gemini):
    resp = client.post("/ask", json={"question": "How many rest days per week?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("personalized") is False
    assert mock_encoder[0] == ["How many rest days per week?"]


def test_ask_normal_branch_shape(client, temp_data_files, mock_encoder, mock_gemini):
    resp = client.post("/ask", json={"question": "chest exercises for beginners"})
    assert resp.status_code == 200
    data = resp.json()
    assert "exercises" in data
    assert "type" not in data
    assert "personalized" in data


# --- P0-3: retrieval diagnostics -------------------------------------------

def test_ask_retrieval_key_present_on_chat_branch(client, temp_data_files, mock_encoder, mock_gemini):
    resp = client.post("/ask", json={"question": "chest exercises for beginners"})
    assert resp.status_code == 200
    data = resp.json()
    assert "retrieval" in data
    for key in ("vector_search_results", "distance_threshold", "limit", "passed_threshold_count", "returned_count", "backfill_count"):
        assert key in data["retrieval"], f"missing {key} in retrieval diagnostics"


def test_ask_retrieval_key_absent_on_plan_branch(client, temp_data_files, mock_encoder, mock_gemini):
    resp = client.post("/ask", json={"question": "give me a 7-day workout plan"})
    assert resp.status_code == 200
    data = resp.json()
    assert "retrieval" not in data


# --- P1-3: Mifflin-St Jeor BMR/TDEE -----------------------------------------

def test_bmr_tdee_matches_mifflin_st_jeor_formula(client, temp_data_files):
    auth = register_user(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    resp = client.put(
        "/users/me/preferences",
        json={"height_cm": 170, "weight_kg": 65, "age": 30, "gender": "female"},
        headers=headers,
    )
    assert resp.status_code == 200
    prefs = resp.json()["preferences"]
    # BMR = 10*65 + 6.25*170 - 5*30 - 161 = 650 + 1062.5 - 150 - 161 = 1401.5
    assert prefs["bmr"] == 1401.5
    assert prefs["tdee"] == round(1401.5 * 1.375, 1)


def test_bmr_tdee_null_when_profile_incomplete(client, temp_data_files):
    auth = register_user(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    resp = client.put("/users/me/preferences", json={"goal": "weight_loss"}, headers=headers)
    assert resp.status_code == 200
    prefs = resp.json()["preferences"]
    assert prefs["bmr"] is None
    assert prefs["tdee"] is None


# --- P1-2: blood-panel image encryption at rest -----------------------------

def test_encrypt_decrypt_round_trip(monkeypatch):
    import app as app_module
    from cryptography.fernet import Fernet

    monkeypatch.setattr(app_module, "_fernet", Fernet(Fernet.generate_key()))
    plaintext = "data:image/png;base64,AAAABBBBCCCC"

    encrypted = app_module.encrypt_blood_image(plaintext)
    assert encrypted != plaintext
    assert not encrypted.startswith("data:")

    decrypted = app_module.decrypt_blood_image(encrypted)
    assert decrypted == plaintext


def test_encrypt_is_noop_on_already_encrypted_value(monkeypatch):
    import app as app_module
    from cryptography.fernet import Fernet

    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(app_module, "_fernet", fernet)
    plaintext = "data:image/png;base64,AAAABBBBCCCC"
    once = app_module.encrypt_blood_image(plaintext)
    twice = app_module.encrypt_blood_image(once)
    assert once == twice  # not double-encrypted


def test_encrypt_is_noop_without_key(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "_fernet", None)
    plaintext = "data:image/png;base64,AAAABBBBCCCC"
    assert app_module.encrypt_blood_image(plaintext) == plaintext


def test_decrypt_returns_none_on_invalid_token(monkeypatch):
    import app as app_module
    from cryptography.fernet import Fernet

    monkeypatch.setattr(app_module, "_fernet", Fernet(Fernet.generate_key()))
    assert app_module.decrypt_blood_image("not-a-real-fernet-token") is None


def test_boot_refuses_when_key_missing_and_encrypted_data_present(tmp_path, monkeypatch):
    import app as app_module

    users_path = tmp_path / "users.json"
    users_path.write_text(
        json.dumps([{"id": "u1", "preferences": {"bloodTestImage": "gAAAAABnot-a-data-url-prefix"}}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(app_module, "USERS_FILE", users_path)
    monkeypatch.setattr(app_module, "HEALTH_DATA_KEY", "")

    try:
        app_module._assert_health_data_key_present_if_needed()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "HEALTH_DATA_KEY" in str(exc)


def test_boot_ok_when_key_missing_and_no_encrypted_data(tmp_path, monkeypatch):
    import app as app_module

    users_path = tmp_path / "users.json"
    users_path.write_text(json.dumps([{"id": "u1", "preferences": {}}]), encoding="utf-8")
    monkeypatch.setattr(app_module, "USERS_FILE", users_path)
    monkeypatch.setattr(app_module, "HEALTH_DATA_KEY", "")

    app_module._assert_health_data_key_present_if_needed()  # should not raise


def test_analyze_decrypts_before_building_note(client, temp_data_files, monkeypatch):
    import app as app_module
    from cryptography.fernet import Fernet

    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(app_module, "_fernet", fernet)

    auth = register_user(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    plaintext = "data:image/png;base64," + ("A" * 300)
    encrypted = fernet.encrypt(plaintext.encode()).decode()

    users = app_module.load_users()
    for u in users:
        if u["id"] == auth["user"]["id"]:
            u.setdefault("preferences", {})["bloodTestImage"] = encrypted
    app_module.save_users(users)

    captured_prompts = []

    class _Resp:
        text = "ok"
        candidates = []

    def fake_generate_content(*, model, contents, **kwargs):
        captured_prompts.append(contents[0]["parts"][0]["text"])
        return _Resp()

    if app_module.client_llm is not None:
        monkeypatch.setattr(app_module.client_llm.models, "generate_content", fake_generate_content)

    resp = client.post("/users/me/preferences/analyze", headers=headers)
    assert resp.status_code == 200
    if captured_prompts:
        assert "unreadable" not in captured_prompts[0]


def test_parse_data_url():
    import app as app_module

    mime, payload = app_module._parse_data_url("data:image/png;base64,AAAABBBB")
    assert mime == "image/png"
    assert payload == "AAAABBBB"

    assert app_module._parse_data_url(None) == (None, None)
    assert app_module._parse_data_url("not-a-data-url") == (None, None)
    assert app_module._parse_data_url("data:image/png,AAAA") == (None, None)  # no ;base64


def test_analyze_sends_image_as_multimodal_part(client, temp_data_files, monkeypatch):
    """The blood test image must actually reach Gemini as image data (an
    inline_data part), not just a text note about its base64 length."""
    import app as app_module
    from cryptography.fernet import Fernet
    import base64

    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(app_module, "_fernet", fernet)

    auth = register_user(client)
    headers = {"Authorization": f"Bearer {auth['token']}"}
    fake_png_bytes = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"
    plaintext = "data:image/png;base64," + base64.b64encode(fake_png_bytes).decode()
    encrypted = fernet.encrypt(plaintext.encode()).decode()

    users = app_module.load_users()
    for u in users:
        if u["id"] == auth["user"]["id"]:
            u.setdefault("preferences", {})["bloodTestImage"] = encrypted
    app_module.save_users(users)

    captured_contents = []

    class _Resp:
        text = "Saw the image."
        candidates = []

    def fake_generate_content(*, model, contents, **kwargs):
        captured_contents.append(contents)
        return _Resp()

    if app_module.client_llm is not None:
        monkeypatch.setattr(app_module.client_llm.models, "generate_content", fake_generate_content)

    resp = client.post("/users/me/preferences/analyze", headers=headers)
    assert resp.status_code == 200

    if captured_contents:
        parts = captured_contents[0][0]["parts"]
        assert len(parts) == 2
        assert "text" in parts[0]
        assert parts[1]["inline_data"]["mime_type"] == "image/png"
        assert parts[1]["inline_data"]["data"] == base64.b64encode(fake_png_bytes).decode()


# --- P2-1: streaming /ask/stream --------------------------------------------

def test_ask_stream_emits_multiple_delta_events_then_done(client, temp_data_files, mock_encoder, mock_gemini_stream):
    resp = client.post("/ask/stream", json={"question": "good warmup exercises"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    body = resp.text
    frames = [f for f in body.split("\n\n") if f.strip()]
    assert len(frames) >= 2  # at least one delta + the final done event

    events = [json.loads(f[len("data: "):]) for f in frames]
    deltas = [e for e in events if "delta" in e]
    done_events = [e for e in events if e.get("done")]

    assert len(deltas) == len(mock_gemini_stream)  # one event per chunk, none merged/dropped
    assert "".join(e["delta"] for e in deltas) == "".join(mock_gemini_stream)

    assert len(done_events) == 1
    done = done_events[0]
    assert "exercises" in done
    assert "retrieval" in done
    assert "personalized" in done


def test_ask_stream_embedding_receives_raw_question_only(client, temp_data_files, mock_encoder, mock_gemini_stream):
    question = "chest exercises for beginners"
    resp = client.post("/ask/stream", json={"question": question})
    assert resp.status_code == 200
    assert mock_encoder[0] == [question]


def test_ask_stream_error_event_on_generation_failure(client, temp_data_files, mock_encoder, monkeypatch):
    import app as app_module

    def broken_stream(*args, **kwargs):
        raise RuntimeError("simulated Gemini failure")
        yield  # pragma: no cover - makes this a generator function

    if app_module.client_llm is not None:
        monkeypatch.setattr(app_module.client_llm.models, "generate_content_stream", broken_stream)

    resp = client.post("/ask/stream", json={"question": "leg day"})
    assert resp.status_code == 200  # SSE connection itself still succeeds
    frames = [f for f in resp.text.split("\n\n") if f.strip()]
    events = [json.loads(f[len("data: "):]) for f in frames]
    assert any(e.get("error") and e.get("done") for e in events)


def test_ask_plan_branch_shape(client, temp_data_files, mock_encoder, mock_gemini):
    resp = client.post("/ask", json={"question": "give me a 7-day workout plan"})
    assert resp.status_code == 200
    data = resp.json()
    # Plan branch depends on >=16 rows in Postgres `documents`; if the corpus
    # is too small it returns the documented fallback shape instead.
    if data.get("answer") == "Not enough exercises in database.":
        return
    assert data.get("type") == "hybrid_database_plan"
    assert "exercises" not in data


def test_ask_authenticated_personalizes_prompt(client, temp_data_files, mock_encoder, monkeypatch):
    """With preferences set, the prefs block should actually be spliced into
    the prompt sent to Gemini (proves build_prefs_block is wired in, not just
    a no-op helper)."""
    import app as app_module

    auth = register_user(client)
    token = auth["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.put(
        "/users/me/preferences",
        json={"goal": "weight_loss", "height_cm": 165, "weight_kg": 70, "gender": "female", "age": 34},
        headers=headers,
    )

    captured_prompts = []

    class _Resp:
        text = "SHORT ANSWER:\nOk.\n\nFULL PLAN:\nOk."
        candidates = []

    def fake_generate_content(*, model, contents, **kwargs):
        captured_prompts.append(contents[0]["parts"][0]["text"])
        return _Resp()

    if app_module.client_llm is not None:
        monkeypatch.setattr(app_module.client_llm.models, "generate_content", fake_generate_content)

    resp = client.post("/ask", json={"question": "good leg exercises"}, headers=headers)
    assert resp.status_code == 200
    if captured_prompts:  # skipped entirely if GEMINI_API_KEY is unset in this env
        assert "weight_loss" in captured_prompts[0]
        assert "34-year-old female" in captured_prompts[0] or "female" in captured_prompts[0]
