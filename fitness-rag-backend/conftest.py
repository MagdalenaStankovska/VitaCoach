"""Shared pytest fixtures for the FastAPI backend test suite.

Importing `app` triggers real startup work (SentenceTransformer load, a
Postgres connection, and loading the exercise corpus into Chroma). That's
accepted here since Postgres is reachable in this dev environment, but it
does mean the suite isn't fully hermetic / offline. Gemini calls and the
embedding model are patched per-test so no network calls or API spend
happen while running the suite.
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient

import app as app_module


@pytest.fixture()
def client():
    return TestClient(app_module.app)


@pytest.fixture()
def temp_data_files(tmp_path, monkeypatch):
    """Redirect USERS_FILE/PLANS_FILE to throwaway files so tests never touch
    the real data/users.json or data/plans.json."""
    users_path = tmp_path / "users.json"
    users_path.write_text("[]", encoding="utf-8")
    plans_path = tmp_path / "plans.json"
    plans_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(app_module, "USERS_FILE", users_path)
    monkeypatch.setattr(app_module, "PLANS_FILE", plans_path)
    return users_path


@pytest.fixture()
def mock_encoder(monkeypatch):
    """Patches app.model.encode to record every call's raw input and return a
    fixed-size zero vector, so tests can assert exactly what reaches the
    encoder without depending on the real model's output."""
    calls = []

    def fake_encode(inputs, *args, **kwargs):
        calls.append(inputs)
        return np.zeros((len(inputs), 384))

    monkeypatch.setattr(app_module.model, "encode", fake_encode)
    return calls


class _FakeGeminiResponse:
    def __init__(self, text):
        self.text = text
        self.candidates = []


@pytest.fixture()
def mock_gemini(monkeypatch):
    """Patches the Gemini text-generation call so tests are deterministic and
    don't spend real API credits. Returns the canned answer text used."""
    canned_text = "SHORT ANSWER:\nTest advice.\n\nFULL PLAN:\nDetailed test plan."

    def fake_generate_content(*args, **kwargs):
        return _FakeGeminiResponse(canned_text)

    if app_module.client_llm is not None:
        monkeypatch.setattr(app_module.client_llm.models, "generate_content", fake_generate_content)

    return canned_text


@pytest.fixture()
def mock_gemini_stream(monkeypatch):
    """Patches the Gemini streaming call with a fake multi-chunk generator,
    so /ask/stream can be tested without real API calls/quota."""
    chunks = ["SHORT ANSWER:\n", "Test ", "streamed ", "advice.\n\n", "FULL PLAN:\n", "Detailed streamed plan."]

    def fake_generate_content_stream(*args, **kwargs):
        for c in chunks:
            yield _FakeGeminiResponse(c)

    if app_module.client_llm is not None:
        monkeypatch.setattr(app_module.client_llm.models, "generate_content_stream", fake_generate_content_stream)

    return chunks


def register_user(client, email="test@example.com", password="testpass123", name="Test User"):
    resp = client.post("/auth/register", json={"name": name, "email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()
