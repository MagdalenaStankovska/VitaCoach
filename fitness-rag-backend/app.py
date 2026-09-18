from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
import chromadb
from google import genai
import os
from dotenv import load_dotenv
import psycopg2
from sentence_transformers import SentenceTransformer
from fastapi.middleware.cors import CORSMiddleware
import requests
import random
import base64
import hashlib
import json
import secrets
import re
import time
from pathlib import Path
from urllib.parse import quote, urlencode
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
from cryptography.fernet import Fernet, InvalidToken

try:
    from garminconnect import Garmin
except Exception:
    Garmin = None

from garmin_adapters import build_garmin_adapter, load_dashboard as _garmin_load_dashboard

# ==========================
# LOAD ENV (GEMINI)
# ==========================
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
GEMINI_MAX_RETRIES = max(0, int(os.getenv("GEMINI_MAX_RETRIES", "2")))
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "imagen-4.0-generate-001")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
USE_AI_EXERCISE_IMAGES = os.getenv("USE_AI_EXERCISE_IMAGES", "1" if api_key else "0").strip() == "1"

print("KEY LOADED:", api_key[:10] if api_key else "missing")

client_llm = genai.Client(api_key=api_key) if api_key else None

# ==========================
# FASTAPI
# ==========================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
PLANS_FILE = DATA_DIR / "plans.json"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_CALENDAR_REDIRECT_URI = os.getenv(
    "GOOGLE_CALENDAR_REDIRECT_URI",
    "http://127.0.0.1:9000/auth/google-calendar/callback",
)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL", "")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD", "")
GARMIN_ADAPTER = os.getenv("GARMIN_ADAPTER", "legacy")
GARMIN_HEALTH_CLIENT_ID = os.getenv("GARMIN_HEALTH_CLIENT_ID", "")
GARMIN_HEALTH_CLIENT_SECRET = os.getenv("GARMIN_HEALTH_CLIENT_SECRET", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
# Local dev default unchanged ("localhost"); Docker Compose overrides this to
# "postgres" (the service name) so the backend container can reach the
# postgres container -- "localhost" inside a container means the container
# itself, not a sibling service.
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# --- Blood-panel image encryption at rest (Fernet) --------------------------
HEALTH_DATA_KEY = os.getenv("HEALTH_DATA_KEY", "")
_fernet = Fernet(HEALTH_DATA_KEY.encode()) if HEALTH_DATA_KEY else None


def _looks_encrypted(value: str) -> bool:
    """Plaintext bloodTestImage values are always data-URLs ("data:...");
    Fernet tokens never start with "data:" — cheap, reliable discriminator
    between legacy plaintext and already-encrypted values."""
    return bool(value) and not value.startswith("data:")


def encrypt_blood_image(plaintext_data_url: str | None) -> str | None:
    """No-op (returns input unchanged) if there's nothing to encrypt, no key
    is configured, or the value already looks encrypted — never raises."""
    if not plaintext_data_url or not _fernet:
        return plaintext_data_url
    if _looks_encrypted(plaintext_data_url):
        return plaintext_data_url
    return _fernet.encrypt(plaintext_data_url.encode()).decode()


def decrypt_blood_image(stored_value: str | None) -> str | None:
    """Degrades to None on any decrypt failure (bad/missing key, corrupt
    token) instead of raising — matches the _safe_garmin_call convention
    applied to a crypto operation instead of a network call."""
    if not stored_value or not _fernet or not _looks_encrypted(stored_value):
        return stored_value
    try:
        return _fernet.decrypt(stored_value.encode()).decode()
    except InvalidToken:
        return None


def _assert_health_data_key_present_if_needed() -> None:
    """Startup guard: refuses to boot with a clear error if HEALTH_DATA_KEY is
    unset while encrypted health data already exists in data/users.json —
    otherwise that data would be silently unreadable forever."""
    if HEALTH_DATA_KEY:
        return
    for existing_user in load_users():
        blood_img = (existing_user.get("preferences") or {}).get("bloodTestImage")
        if blood_img and _looks_encrypted(blood_img):
            raise SystemExit(
                "HEALTH_DATA_KEY is unset but encrypted health data exists in "
                "data/users.json. Set HEALTH_DATA_KEY before starting the app."
            )


GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def haversine_distance_km(lon1, lat1, lon2, lat2):
    try:
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6371 * c
    except Exception:
        return float("inf")


def ensure_json_file(path: Path, default_value):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default_value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_file(path: Path, default_value):
    ensure_json_file(path, default_value)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default_value


def save_json_file(path: Path, payload):
    ensure_json_file(path, payload)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def load_users():
    return load_json_file(USERS_FILE, [])


def save_users(users):
    save_json_file(USERS_FILE, users)


def load_plans():
    return load_json_file(PLANS_FILE, {})


def save_plans(plans):
    save_json_file(PLANS_FILE, plans)


def frontend_redirect_url(path="/", params=None):
    base = FRONTEND_URL.rstrip("/")
    final_path = path if path.startswith("/") else f"/{path}"
    url = f"{base}{final_path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return url


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def hash_password(password: str) -> str:
    return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "googleCalendarConnected": bool(user.get("googleCalendarConnected", False)),
        "garminConnected": bool(user.get("garminConnected", False)),
    }


def require_google_oauth_config():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google Calendar OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )


def find_user_by_id(user_id: str):
    for user in load_users():
        if user.get("id") == user_id:
            return user
    return None


def find_user_by_google_state(state: str):
    for user in load_users():
        if user.get("googleCalendarOAuthState") == state:
            return user
    return None


def store_google_state(user_id: str, state: str):
    users = load_users()
    updated_user = None
    for existing in users:
        if existing.get("id") == user_id:
            existing["googleCalendarOAuthState"] = state
            existing["googleCalendarOAuthStateIssuedAt"] = int(time.time())
            updated_user = existing
            break
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    save_users(users)
    return updated_user


def clear_google_state(user_id: str):
    users = load_users()
    for existing in users:
        if existing.get("id") == user_id:
            existing.pop("googleCalendarOAuthState", None)
            existing.pop("googleCalendarOAuthStateIssuedAt", None)
            save_users(users)
            return existing
    return None


def build_google_calendar_auth_url(user: dict):
    require_google_oauth_config()
    state = secrets.token_urlsafe(24)
    store_google_state(user["id"], state)

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_CALENDAR_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_CALENDAR_SCOPES),
        "access_type": "offline",
        "prompt": "consent select_account",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def finalize_google_calendar_connection(code: str, state: str):
    require_google_oauth_config()

    user = find_user_by_google_state(state)
    if not user:
        raise HTTPException(status_code=400, detail="Google connection session expired or is invalid.")

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_CALENDAR_REDIRECT_URI,
        },
        timeout=30,
    )
    try:
        token_data = token_response.json()
    except Exception:
        token_data = {}

    if not token_response.ok:
        error_message = token_data.get("error_description") or token_data.get("error") or "Google token exchange failed."
        raise HTTPException(status_code=400, detail=error_message)

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google did not return an access token.")

    users = load_users()
    updated_user = None
    now = int(time.time())
    for existing in users:
        if existing.get("id") == user.get("id"):
            existing["googleCalendarConnected"] = True
            existing.pop("googleCalendarOAuthState", None)
            existing.pop("googleCalendarOAuthStateIssuedAt", None)
            existing["googleCalendarAccessToken"] = access_token
            if token_data.get("refresh_token"):
                existing["googleCalendarRefreshToken"] = token_data.get("refresh_token")
            existing["googleCalendarTokenType"] = token_data.get("token_type", "Bearer")
            existing["googleCalendarScopes"] = token_data.get("scope", " ".join(GOOGLE_CALENDAR_SCOPES))
            expires_in = token_data.get("expires_in")
            existing["googleCalendarTokenExpiresAt"] = now + int(expires_in) if expires_in else None
            existing["googleCalendarConnectedAt"] = now
            updated_user = existing
            break

    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found.")

    save_users(users)
    return updated_user


def find_user_by_token(token: str | None):
    if not token:
        return None

    for user in load_users():
        if user.get("token") == token:
            return user
    return None


def require_user(authorization: str | None = Header(default=None)):
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    user = find_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user


def optional_user(authorization: str | None = Header(default=None)):
    """Like require_user, but never raises — returns None for missing/invalid tokens
    so endpoints can support both authenticated and anonymous callers."""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    return find_user_by_token(token)


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class PlanPayload(BaseModel):
    items: list = Field(default_factory=list)


class GarminConnectRequest(BaseModel):
    email: str | None = None
    password: str | None = None


class CreateCalendarEventRequest(BaseModel):
    title: str
    description: str | None = None
    startTime: str  # ISO 8601 format
    endTime: str | None = None  # ISO 8601 format
    location: str | None = None


def upsert_user(updated_user: dict):
    users = load_users()
    replaced = False
    next_users = []
    for user in users:
        if user.get("id") == updated_user.get("id"):
            next_users.append(updated_user)
            replaced = True
        else:
            next_users.append(user)
    if not replaced:
        next_users.append(updated_user)
    save_users(next_users)


def sanitize_plan_items(items):
    sanitized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        cleaned = {k: v for k, v in item.items() if k != "images"}
        sanitized.append(cleaned)
    return sanitized


def _connect_to_garmin(email: str, password: str):
    if Garmin is None:
        raise HTTPException(
            status_code=500,
            detail="garminconnect package is not installed. Run: pip install garminconnect",
        )

    try:
        api = Garmin(email, password)
        api.login()
        today_iso = datetime.utcnow().date().isoformat()
        summary = api.get_user_summary(today_iso) or {}
        return {
            "fullName": api.get_full_name(),
            "steps": summary.get("totalSteps"),
            "calories": summary.get("totalKilocalories"),
            "rawSummary": summary,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Garmin connection failed: {exc}") from exc


def _load_garmin_dashboard(email: str, password: str):
    """Builds a GarminAdapter per GARMIN_ADAPTER (legacy by default) and
    assembles the dashboard through its 5-method interface. Behavior for the
    default "legacy" adapter is unchanged from before this refactor — same
    single get_user_summary fetch backing steps/active-calories/distance,
    same _safe_garmin_call-wrapped calls underneath (see garmin_adapters.py)."""
    if GARMIN_ADAPTER.lower() == "legacy" and Garmin is None:
        raise HTTPException(
            status_code=500,
            detail="garminconnect package is not installed. Run: pip install garminconnect",
        )

    try:
        adapter = build_garmin_adapter(
            email, password, GARMIN_ADAPTER, GARMIN_HEALTH_CLIENT_ID, GARMIN_HEALTH_CLIENT_SECRET
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Garmin login failed: {exc}") from exc

    try:
        return _garmin_load_dashboard(adapter)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Garmin dashboard fetch failed: {exc}") from exc


@app.post("/auth/register")
def auth_register(payload: RegisterRequest):
    name = str(payload.name or "").strip()
    email = normalize_email(payload.email)
    password = str(payload.password or "")

    if not name or not email or not password:
        raise HTTPException(status_code=400, detail="Name, email and password are required.")

    users = load_users()
    if any(normalize_email(user.get("email")) == email for user in users):
        raise HTTPException(status_code=400, detail="This email is already registered.")

    user = {
        "id": secrets.token_hex(8),
        "name": name,
        "email": email,
        "passwordHash": hash_password(password),
        "token": new_token(),
        "googleCalendarConnected": False,
        "garminConnected": False,
    }

    users.append(user)
    save_users(users)

    plans = load_plans()
    plans.setdefault(user["id"], [])
    save_plans(plans)

    return {"token": user["token"], "user": public_user(user)}


@app.post("/auth/login")
def auth_login(payload: LoginRequest):
    email = normalize_email(payload.email)
    password = str(payload.password or "")

    users = load_users()
    for user in users:
        if normalize_email(user.get("email")) == email and user.get("passwordHash") == hash_password(password):
            user["token"] = new_token()
            save_users(users)
            return {"token": user["token"], "user": public_user(user)}

    raise HTTPException(status_code=401, detail="Invalid email or password.")


@app.get("/auth/me")
def auth_me(user=Depends(require_user)):
    return {"user": public_user(user)}


@app.post("/auth/logout")
def auth_logout(user=Depends(require_user)):
    users = load_users()
    for existing in users:
        if existing.get("id") == user.get("id"):
            existing["token"] = ""
            break
    save_users(users)
    return {"ok": True}


@app.get("/users/me/plan")
def get_my_plan(user=Depends(require_user)):
    plans = load_plans()
    return {"items": plans.get(user["id"], [])}


@app.put("/users/me/plan")
def save_my_plan(payload: PlanPayload, user=Depends(require_user)):
    plans = load_plans()
    plans[user["id"]] = sanitize_plan_items(payload.items)
    save_plans(plans)
    return {"items": plans[user["id"]]}


class PreferencesPayload(BaseModel):
    goal: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    gender: str | None = None
    age: int | None = None
    bloodTestImage: str | None = None  # data URL (base64)


def _preferences_response(prefs: dict) -> dict:
    """Adds derived (never persisted) bmr/tdee to a preferences dict for API
    responses, so they're always computed fresh from the latest
    height/weight/age/gender and can never go stale."""
    bmr, tdee = compute_bmr_tdee(
        prefs.get("height_cm"), prefs.get("weight_kg"), prefs.get("age"), prefs.get("gender")
    )
    return {"preferences": {**prefs, "bmr": bmr, "tdee": tdee}}


@app.get("/users/me/preferences")
def get_my_preferences(user=Depends(require_user)):
    """Return stored preferences for current user."""
    return _preferences_response(user.get("preferences", {}))


@app.put("/users/me/preferences")
def save_my_preferences(payload: PreferencesPayload, user=Depends(require_user)):
    """Save user's preferences into the users.json store."""
    users = load_users()
    updated_user = None
    for existing in users:
        if existing.get("id") == user.get("id"):
            existing.setdefault("preferences", {})
            # store only the allowed keys
            prefs = existing["preferences"]
            if payload.goal is not None:
                prefs["goal"] = payload.goal
            if payload.height_cm is not None:
                prefs["height_cm"] = payload.height_cm
            if payload.weight_kg is not None:
                prefs["weight_kg"] = payload.weight_kg
            if payload.gender is not None:
                prefs["gender"] = payload.gender
            if payload.age is not None:
                prefs["age"] = payload.age
            if payload.bloodTestImage is not None:
                prefs["bloodTestImage"] = encrypt_blood_image(payload.bloodTestImage)
            existing["preferences"] = prefs
            updated_user = existing
            break

    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found.")

    save_users(users)
    return _preferences_response(updated_user.get("preferences", {}))


def _parse_data_url(data_url: str | None):
    """Splits a "data:<mime>;base64,<payload>" string into (mime_type, base64_payload).
    Returns (None, None) on anything that doesn't look like a well-formed data URL —
    never raises, matches the codebase's degrade-not-raise convention."""
    if not data_url or not data_url.startswith("data:") or "," not in data_url:
        return None, None
    header, payload = data_url.split(",", 1)
    if ";base64" not in header:
        return None, None
    mime_type = header[len("data:"):].split(";", 1)[0] or "application/octet-stream"
    return mime_type, payload


@app.post("/users/me/preferences/analyze")
def analyze_preferences(user=Depends(require_user)):
    """Use the Gemini model to analyze stored preferences and an optional blood-test image.

    If a readable blood-test image is on file, it is decrypted and sent to Gemini as
    real image data (multimodal vision call) so the model can actually read it —
    not just a text note about its length, as before.
    """
    prefs = user.get("preferences", {})
    if not client_llm:
        raise HTTPException(status_code=500, detail="Gemini API key is not configured on the server.")

    goal = prefs.get("goal") or "unspecified"
    height = prefs.get("height_cm")
    weight = prefs.get("weight_kg")
    gender = prefs.get("gender")
    blood_img_encrypted = prefs.get("bloodTestImage")
    blood_img = decrypt_blood_image(blood_img_encrypted) if blood_img_encrypted else None

    image_parts = None
    img_note = "no blood test image provided"
    if blood_img_encrypted and blood_img is None:
        img_note = "blood test image present but unreadable (decryption failed)"
    elif blood_img:
        mime_type, b64_payload = _parse_data_url(blood_img)
        if mime_type and b64_payload:
            image_parts = [{"inline_data": {"mime_type": mime_type, "data": b64_payload}}]
            img_note = "a blood test panel image is attached below — read the values directly from it"
        else:
            img_note = "blood test image present but in an unrecognized format"

    prompt_lines = [
        "You are a certified medical-informed nutrition coach.",
        "Analyze the following user data and provide actionable dietary and training recommendations.",
        "User preferences and info:",
        f"- Goal: {goal}",
        f"- Height (cm): {height}",
        f"- Weight (kg): {weight}",
        f"- Gender: {gender}",
        f"- {img_note}",
        (
            "If a blood test image is attached, read the actual marker names and values "
            "from it and reference specific ones (e.g. cholesterol, glucose, vitamin D, "
            "iron/ferritin) in your recommendations, flagging anything outside a typical "
            "healthy range as a conservative, non-diagnostic observation. If no image is "
            "attached, state what markers you'd want to see instead."
            if image_parts
            else "No blood test image is attached — state what markers you'd want to see instead."
        ),
        "Provide:\n1) Short summary of relevant focus points\n2) Nutritional recommendations\n3) Training emphasis\n4) If blood-test values are visible, list the specific markers/values you read and how they inform the recommendations above.\nAnswer concisely and clearly."
    ]

    prompt = "\n".join([str(l) for l in prompt_lines])
    try:
        text, err = _generate_text_with_retry(prompt, image_parts=image_parts)
        if not text:
            raise HTTPException(status_code=500, detail=f"AI analysis failed: {err}")
        return {"analysis": text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")


@app.post("/users/me/connections/{service_name}")
def connect_service(service_name: str, user=Depends(require_user)):
    field_map = {
        "garmin": "garminConnected",
    }

    if service_name == "google-calendar":
        return {"authUrl": build_google_calendar_auth_url(user)}

    if service_name == "garmin":
        email = GARMIN_EMAIL.strip()
        password = GARMIN_PASSWORD
        if not email or not password:
            raise HTTPException(
                status_code=400,
                detail="GARMIN_EMAIL/GARMIN_PASSWORD are not set. Use /users/me/connections/garmin/test with credentials in the request body.",
            )

        details = _connect_to_garmin(email, password)

        users = load_users()
        updated_user = None
        now = int(time.time())
        for existing in users:
            if existing.get("id") == user.get("id"):
                existing["garminConnected"] = True
                existing["garminConnectedAt"] = now
                existing["garminEmail"] = email
                updated_user = existing
                break

        if updated_user is not None:
            save_users(users)
            return {
                "user": public_user(updated_user),
                "garmin": {
                    "fullName": details.get("fullName"),
                    "steps": details.get("steps"),
                    "calories": details.get("calories"),
                },
            }

        raise HTTPException(status_code=404, detail="User not found.")

    if service_name not in field_map:
        raise HTTPException(status_code=400, detail="Unknown service.")

    users = load_users()
    updated_user = None
    for existing in users:
        if existing.get("id") == user.get("id"):
            existing[field_map[service_name]] = True
            updated_user = existing
            break

    if updated_user is not None:
        save_users(users)
        return {"user": public_user(updated_user)}

    raise HTTPException(status_code=404, detail="User not found.")


@app.post("/users/me/connections/garmin/test")
def connect_garmin_test(payload: GarminConnectRequest, user=Depends(require_user)):
    email = (payload.email or GARMIN_EMAIL).strip()
    password = payload.password or GARMIN_PASSWORD

    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail="Missing Garmin credentials. Provide email/password in body or set GARMIN_EMAIL/GARMIN_PASSWORD in .env.",
        )

    details = _connect_to_garmin(email, password)

    users = load_users()
    updated_user = None
    now = int(time.time())
    for existing in users:
        if existing.get("id") == user.get("id"):
            existing["garminConnected"] = True
            existing["garminConnectedAt"] = now
            existing["garminEmail"] = email
            updated_user = existing
            break

    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found.")

    save_users(users)

    return {
        "connected": True,
        "user": public_user(updated_user),
        "garmin": {
            "fullName": details.get("fullName"),
            "steps": details.get("steps"),
            "calories": details.get("calories"),
        },
    }


@app.get("/users/me/garmin/dashboard")
def get_garmin_dashboard(user=Depends(require_user)):
    if not user.get("garminConnected"):
        return {
            "connected": False,
            "error": "Garmin is not connected for this user.",
            "dashboard": None,
        }

    email = (user.get("garminEmail") or GARMIN_EMAIL).strip()
    password = GARMIN_PASSWORD
    if not email or not password:
        return {
            "connected": False,
            "error": "Garmin credentials are missing in backend .env.",
            "dashboard": None,
        }

    try:
        dashboard = _load_garmin_dashboard(email, password)
        return {"connected": True, "dashboard": dashboard}
    except HTTPException as exc:
        return {"connected": False, "error": str(exc.detail), "dashboard": None}


@app.get("/auth/google-calendar/callback")
def google_calendar_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(
            frontend_redirect_url("/", {"googleCalendar": "error", "message": error}),
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            frontend_redirect_url("/", {"googleCalendar": "error", "message": "Missing Google authorization data."}),
            status_code=302,
        )

    try:
        finalize_google_calendar_connection(code, state)
    except HTTPException as exc:
        clear_user = find_user_by_google_state(state)
        if clear_user:
            clear_google_state(clear_user["id"])
        return RedirectResponse(
            frontend_redirect_url("/", {"googleCalendar": "error", "message": str(exc.detail)}),
            status_code=302,
        )

    return RedirectResponse(
        frontend_redirect_url("/", {"googleCalendar": "connected"}),
        status_code=302,
    )


# ==========================
# GOOGLE CALENDAR INTEGRATION
# ==========================
def refresh_google_calendar_token(user: dict):
    """Refresh Google Calendar access token if expired."""
    if not user.get("googleCalendarConnected"):
        return None
    
    expires_at = user.get("googleCalendarTokenExpiresAt", 0)
    now = int(time.time())
    
    # If token expires in less than 5 minutes, refresh it
    if expires_at and expires_at - now > 300:
        return user.get("googleCalendarAccessToken")
    
    refresh_token = user.get("googleCalendarRefreshToken")
    if not refresh_token:
        return None
    
    require_google_oauth_config()
    
    try:
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        
        token_data = token_response.json()
        if not token_response.ok:
            return None

        access_token = token_data.get("access_token")
        if access_token:
            # Update user's access token
            users = load_users()
            for existing in users:
                if existing.get("id") == user.get("id"):
                    existing["googleCalendarAccessToken"] = access_token
                    if token_data.get("expires_in"):
                        existing["googleCalendarTokenExpiresAt"] = now + int(token_data.get("expires_in"))
                    break
            save_users(users)
            return access_token
    except Exception as e:
        print(f"[GOOGLE CALENDAR] Token refresh failed: {e}")
    
    return None


def fetch_google_calendar_events(user: dict, days_ahead: int = 7):
    """Fetch Google Calendar events for the next N days."""
    if not user.get("googleCalendarConnected"):
        raise HTTPException(status_code=400, detail="Google Calendar is not connected.")
    
    access_token = refresh_google_calendar_token(user)
    if not access_token:
        access_token = user.get("googleCalendarAccessToken")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="No valid Google Calendar token.")
    
    try:
        now = datetime.utcnow()
        future = now + timedelta(days=days_ahead)
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        
        params = {
            "timeMin": now.isoformat() + "Z",
            "timeMax": future.isoformat() + "Z",
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 50,
        }
        
        response = requests.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            params=params,
            timeout=30,
        )
        
        if not response.ok:
            try:
                error_payload = response.json()
            except Exception:
                error_payload = response.text
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch calendar events. {error_payload}",
            )
        
        events_data = response.json()
        events = []
        
        for event in events_data.get("items", []):
            start = event.get("start", {})
            end = event.get("end", {})
            
            events.append({
                "id": event.get("id"),
                "title": event.get("summary", "Untitled Event"),
                "description": event.get("description", ""),
                "startTime": start.get("dateTime") or start.get("date"),
                "endTime": end.get("dateTime") or end.get("date"),
                "location": event.get("location", ""),
            })
        
        return events
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GOOGLE CALENDAR] Fetch failed: {e}")
        raise HTTPException(status_code=500, detail=f"Calendar fetch error: {str(e)}")


@app.get("/users/me/calendar/events")
def get_calendar_events(days_ahead: int = 7, user=Depends(require_user)):
    """Get user's Google Calendar events."""
    try:
        events = fetch_google_calendar_events(user, days_ahead)
        return {"events": events, "connected": True}
    except HTTPException as exc:
        detail = str(exc.detail)
        if exc.status_code in (400, 401, 403) or "not connected" in detail.lower():
            return {"events": [], "connected": False, "error": detail}
        return {"events": [], "connected": False, "error": "Calendar temporarily unavailable."}


def create_google_calendar_event(user: dict, event_data: CreateCalendarEventRequest):
    """Create an event in user's Google Calendar."""
    if not user.get("googleCalendarConnected"):
        raise HTTPException(status_code=400, detail="Google Calendar is not connected.")
    
    access_token = refresh_google_calendar_token(user)
    if not access_token:
        access_token = user.get("googleCalendarAccessToken")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="No valid Google Calendar token.")
    
    try:
        # Build the event object
        event_body = {
            "summary": event_data.title,
            "start": {"dateTime": event_data.startTime},
        }
        
        if event_data.description:
            event_body["description"] = event_data.description
        
        if event_data.endTime:
            event_body["end"] = {"dateTime": event_data.endTime}
        else:
            # Default to 1 hour duration if no end time provided
            start_dt = datetime.fromisoformat(event_data.startTime.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(hours=1)
            event_body["end"] = {"dateTime": end_dt.isoformat()}
        
        if event_data.location:
            event_body["location"] = event_data.location
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        response = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            json=event_body,
            timeout=30,
        )
        
        if not response.ok:
            try:
                error_payload = response.json()
            except Exception:
                error_payload = response.text
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to create calendar event. {error_payload}",
            )
        
        created_event = response.json()
        return {
            "success": True,
            "eventId": created_event.get("id"),
            "eventUrl": created_event.get("htmlLink"),
            "title": created_event.get("summary"),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GOOGLE CALENDAR] Event creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Calendar event creation error: {str(e)}")


@app.post("/users/me/calendar/events")
def create_calendar_event(payload: CreateCalendarEventRequest, user=Depends(require_user)):
    """Create an event in user's Google Calendar."""
    try:
        result = create_google_calendar_event(user, payload)
        return result
    except HTTPException as exc:
        raise exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event creation failed: {str(e)}")


class ScheduleAnalysisRequest(BaseModel):
    daysAhead: int = Field(default=7, ge=1, le=30)
    language: str = Field(default="English")
    userLatitude: float | None = Field(default=None)
    userLongitude: float | None = Field(default=None)


def find_nearest_restaurants(user_lat, user_lng, limit=3):
    """Find top nearest restaurants to user's coordinates using Haversine formula."""
    if user_lat is None or user_lng is None:
        return []
    
    try:
        restaurants_file = BASE_DIR / "restaurants_dataset.json"
        if not restaurants_file.exists():
            return []
        
        with open(restaurants_file, "r", encoding="utf-8") as f:
            restaurants = json.load(f)
        
        if not isinstance(restaurants, list):
            return []
        
        ranked = []
        
        for restaurant in restaurants:
            if not restaurant.get("latitude") or not restaurant.get("longitude"):
                continue
            
            distance = haversine_distance_km(
                user_lng,
                user_lat,
                restaurant.get("longitude"),
                restaurant.get("latitude")
            )
            
            ranked.append({
                **restaurant,
                "distance_km": round(distance, 2)
            })

        ranked.sort(key=lambda r: r.get("distance_km", float("inf")))
        return ranked[:max(1, int(limit or 3))]
    except Exception as e:
        print(f"[NEAREST RESTAURANTS] Error: {e}")
        return []


def find_nearest_gyms(user_lat, user_lng, limit=3):
    """Find top nearest gyms/training spots from gyms_dataset.json."""
    if user_lat is None or user_lng is None:
        return []

    try:
        gyms_file = BASE_DIR / "gyms_dataset.json"
        if not gyms_file.exists():
            return []

        with open(gyms_file, "r", encoding="utf-8") as f:
            gyms = json.load(f)

        if not isinstance(gyms, list):
            return []

        ranked = []
        for gym in gyms:
            lat = gym.get("latitude")
            lng = gym.get("longitude")
            if lat is None or lng is None:
                continue

            distance = haversine_distance_km(user_lng, user_lat, lng, lat)
            ranked.append({**gym, "distance_km": round(distance, 2)})

        ranked.sort(key=lambda g: g.get("distance_km", float("inf")))
        return ranked[:max(1, int(limit or 3))]
    except Exception as e:
        print(f"[NEAREST GYMS] Error: {e}")
        return []


def _safe_generate_schedule_text(prompt: str):
    if not client_llm:
        return None, "Gemini API key is missing"

    last_error = ""
    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            resp = client_llm.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
            )
            text = extract_text(resp)
            if text:
                return text, ""
            last_error = "Empty AI response"
        except Exception as e:
            last_error = str(e)
            upper = last_error.upper()
            retryable = any(token in upper for token in ["503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE"])
            print(f"[GEMINI] attempt={attempt + 1} failed: {last_error}")
            if retryable and attempt < GEMINI_MAX_RETRIES:
                time.sleep(1 + attempt)
                continue
            break

    return None, last_error or "AI request failed"


def _fallback_week_plan(days_ahead: int, language: str, nearest_restaurants: list, nearest_gyms: list, calendar_note: str = ""):
    today = datetime.utcnow().date()
    days = [today + timedelta(days=i) for i in range(days_ahead)]

    if language == "Macedonian":
        gym_tip = nearest_gyms[0].get("name") if nearest_gyms else "најблиска теретана"
        food_tip = nearest_restaurants[0].get("name") if nearest_restaurants else "блиски Korpa ресторани"
        intro = "Неделен план (fallback)"
        notes = f"{calendar_note}\n" if calendar_note else ""
        lines = [intro, notes]
        for d in days:
            heading = f"{d.strftime('%A')} ({d.isoformat()}):"
            lines.extend([
                heading,
                "- Тренинг: 30-45 минути (комбинација кардио + сила).",
                f"- Локација: {gym_tip}.",
                f"- Исхрана: брз и балансиран оброк од {food_tip}.",
                "- Вода: минимум 2 литри во текот на денот.",
                "",
            ])
        return "\n".join(lines).strip()

    gym_tip = nearest_gyms[0].get("name") if nearest_gyms else "your nearest gym"
    food_tip = nearest_restaurants[0].get("name") if nearest_restaurants else "nearby Korpa restaurants"
    intro = "Weekly plan (fallback)"
    notes = f"{calendar_note}\n" if calendar_note else ""
    lines = [intro, notes]
    for d in days:
        heading = f"{d.strftime('%A')} ({d.isoformat()}):"
        lines.extend([
            heading,
            "- Workout: 30-45 minutes (mix of cardio and strength).",
            f"- Training spot: {gym_tip}.",
            f"- Meal plan: pick a balanced quick meal from {food_tip}.",
            "- Hydration: at least 2 liters of water.",
            "",
        ])
    return "\n".join(lines).strip()


@app.post("/users/me/schedule-recommendations")
def get_schedule_recommendations(payload: ScheduleAnalysisRequest, user=Depends(require_user)):
    """
    Analyze user's Google Calendar and provide AI-powered recommendations for:
    - When to exercise
    - When to eat
    - What meals to order from nearby Korpa restaurants
    """
    try:
        # Always compute nearby places even when calendar is disconnected/loading.
        nearest_restaurants = []
        nearest_restaurant = None
        nearest_gyms = []
        nearest_gym = None
        restaurant_info = ""
        gym_info = ""

        if payload.userLatitude is not None and payload.userLongitude is not None:
            nearest_restaurants = find_nearest_restaurants(payload.userLatitude, payload.userLongitude, limit=3)
            if nearest_restaurants:
                nearest_restaurant = nearest_restaurants[0]
                nearby_lines = []
                for idx, restaurant in enumerate(nearest_restaurants, start=1):
                    nearby_lines.append(
                        f"{idx}. {restaurant.get('name')} ({restaurant.get('distance_km')} km) - {restaurant.get('address')} - {restaurant.get('url')}"
                    )
                restaurant_info = "\n\nTOP 3 NEAREST RESTAURANTS:\n" + "\n".join(nearby_lines)

            nearest_gyms = find_nearest_gyms(payload.userLatitude, payload.userLongitude, limit=3)
            if nearest_gyms:
                nearest_gym = nearest_gyms[0]
                gym_lines = []
                for idx, gym in enumerate(nearest_gyms, start=1):
                    gym_lines.append(
                        f"{idx}. {gym.get('name')} ({gym.get('distance_km')} km) - {gym.get('address')} - {gym.get('url')}"
                    )
                gym_info = "\n\nTOP 3 NEAREST GYMS/TRAINING SPOTS:\n" + "\n".join(gym_lines)

        events = []
        calendar_connected = bool(user.get("googleCalendarConnected"))
        calendar_error = ""
        try:
            events = fetch_google_calendar_events(user, payload.daysAhead)
            calendar_connected = True
        except HTTPException as exc:
            calendar_connected = False
            calendar_error = str(exc.detail)
            print(f"[SCHEDULE] Continuing without calendar events: {calendar_error}")
        
        # Format events for Gemini
        if events:
            events_text = "\n".join([
                f"- {ev['title']} ({ev['startTime']} to {ev['endTime']}): {ev.get('description', '')}"
                for ev in events
            ])
        else:
            events_text = "No calendar events available. Build a practical weekly plan anyway."
        
        # Load Korpa meals data if available
        korpa_meals = []
        try:
            meals_path = BASE_DIR / "foods_dataset_enriched.json"
            if meals_path.exists():
                with open(meals_path, "r", encoding="utf-8") as f:
                    meals_data = json.load(f)
                    if isinstance(meals_data, list):
                        korpa_meals = meals_data[:50]  # Use first 50 meals as examples
        except Exception as e:
            print(f"[MEALS] Load error: {e}")
        
        meals_text = ""
        if korpa_meals:
            meals_text = "\nAvailable Meals from Korpa:\n"
            for meal in korpa_meals[:20]:
                name = meal.get("name", "Meal")
                prep_time = meal.get("prep_time", "30 min")
                meals_text += f"- {name} (Prep: {prep_time})\n"
        
        # Build prompt for Gemini
        lang = payload.language if payload.language in ["English", "Macedonian"] else "English"
        prefs_block = build_prefs_block(user)

        prompt = f"""
You are a certified personal trainer and nutrition expert.

{prefs_block}

Analyze the user's Google Calendar schedule for the next {payload.daysAhead} days:

{events_text}

{meals_text}

{restaurant_info}

{gym_info}

Based on their schedule, provide:

1. OPTIMAL EXERCISE TIMES: 
   - Identify the best times to work out based on their availability
   - Suggest duration and intensity (short vs. long workouts)
   - List which days have enough time for exercise

2. MEAL TIMING RECOMMENDATIONS:
   - Suggest optimal meal times based on their schedule
   - Note any busy periods where quick meals are needed
   - Recommend pre/post-workout meal timing

3. QUICK MEAL SUGGESTIONS:
   - For busy periods where cooking is not possible
   - If a nearby restaurant is available, recommend ordering from there
   - Provide specific meal recommendations with their prep times
   - Suggest nutritious quick options

4. WEEKLY OVERVIEW:
   - Summarize the best training and nutrition strategy for their week
   - Highlight any scheduling conflicts to avoid
   - If nearby restaurant is provided, suggest which days/times to order from there

Please respond in {lang} language ONLY.
Create day-by-day suggestions for the next {payload.daysAhead} days.
For each day, use this exact heading format:
Monday (YYYY-MM-DD):
Then 3-5 bullet lines under each day.
Prefer nearby gyms and nearby Korpa options when available.
"""
        
        recommendations, ai_error = _safe_generate_schedule_text(prompt)
        if not recommendations:
            note = ""
            if ai_error and "UNAVAILABLE" in ai_error.upper():
                note = "AI service is currently busy; showing fallback weekly plan."
            recommendations = _fallback_week_plan(
                payload.daysAhead,
                lang,
                nearest_restaurants,
                nearest_gyms,
                calendar_note=note,
            )
        
        # Extract quick suggestions (parse the response)
        suggestions = []
        if "EXERCISE TIMES" in recommendations.upper():
            suggestions.append("✅ Personalized workout schedule generated based on your calendar")
        if "MEAL" in recommendations.upper():
            suggestions.append("🍽️ Meal timing recommendations provided")
        if nearest_restaurant:
            suggestions.append(f"📍 Closest restaurant: {nearest_restaurant.get('name')} ({nearest_restaurant.get('distance_km')} km away)")
        if len(nearest_restaurants) > 1:
            suggestions.append(f"🍴 {len(nearest_restaurants)} nearby options found")
        if nearest_gym:
            suggestions.append(f"🏋️ Closest gym/training spot: {nearest_gym.get('name')} ({nearest_gym.get('distance_km')} km away)")
        
        return {
            "recommendations": recommendations,
            "suggestions": suggestions or ["📅 Schedule analysis complete"],
            "events_analyzed": len(events),
            "meals": [{"name": m.get("name"), "prep_time": m.get("prep_time")} for m in korpa_meals[:10]],
            "calendarConnected": calendar_connected,
            "calendarError": calendar_error,
            "nearestRestaurant": nearest_restaurant,
            "nearestRestaurants": nearest_restaurants,
            "nearestGym": nearest_gym,
            "nearestGyms": nearest_gyms,
            "nearestTrainingSpots": nearest_gyms,
            "userLocation": {
                "latitude": payload.userLatitude,
                "longitude": payload.userLongitude
            }
        }
    
    except HTTPException as exc:
        raise exc
    except Exception as e:
        print(f"[SCHEDULE] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Schedule analysis error: {str(e)}")


# ==========================
# EMBEDDING MODEL
# ==========================
model = SentenceTransformer("all-MiniLM-L6-v2")

# ==========================
# CHROMA VECTOR DB
# ==========================
# Local dev (no env vars set): today's in-memory, ephemeral client, rebuilt
# from Postgres on every boot — unchanged default behavior. In Docker, the
# backend service is given CHROMA_HOST/CHROMA_PORT and talks to the
# standalone chroma container instead, so the index survives restarts.
_chroma_host = os.getenv("CHROMA_HOST", "")
if _chroma_host:
    client = chromadb.HttpClient(host=_chroma_host, port=int(os.getenv("CHROMA_PORT", "8000")))
else:
    client = chromadb.Client()
# Explicit distance space: Chroma silently defaults to l2 (squared Euclidean,
# range [0,4] on normalized vectors) when no metadata is given. Under cosine
# the range is [0,2], which would make DISTANCE_THRESHOLD=2.0 below inert —
# make the assumption explicit instead of relying on the silent default.
collection = client.get_or_create_collection(name="fitness", metadata={"hnsw:space": "l2"})


def _assert_collection_space_is_l2(coll) -> None:
    """Startup check: confirms the collection's configured HNSW distance
    space actually is l2. Logs a loud warning (does not crash the app) if
    it's anything else, since that would silently make DISTANCE_THRESHOLD
    inert — exactly the reviewer's objection."""
    space = None
    try:
        config = getattr(coll, "configuration_json", None)
        if config:
            space = (config.get("hnsw") or {}).get("space")
        if space is None:
            space = (coll.metadata or {}).get("hnsw:space")
    except Exception as e:
        print(f"[WARNING] Could not verify Chroma collection distance space: {e}")
        return

    if space != "l2":
        print(
            f"[WARNING] Chroma collection 'fitness' is configured with distance "
            f"space '{space}', not 'l2'. DISTANCE_THRESHOLD is calibrated for "
            f"l2's [0,4] range; under '{space}' it may filter nothing or "
            f"everything. Investigate before trusting retrieval numbers."
        )
    else:
        print("[STARTUP] Chroma collection 'fitness' distance space confirmed: l2")


_assert_collection_space_is_l2(collection)


YOUTUBE_KEY = os.getenv("YOUTUBE_API_KEY")
EXERCISE_RECOMMENDATION_LIMIT = int(os.getenv("EXERCISE_RECOMMENDATION_LIMIT", "8"))
VECTOR_SEARCH_RESULTS = int(os.getenv("VECTOR_SEARCH_RESULTS", "24"))
DISTANCE_THRESHOLD = float(os.getenv("DISTANCE_THRESHOLD", "2.0"))
YOUTUBE_FALLBACK = "https://www.youtube.com/embed/_l3ySVKYVJ8"
IMAGE_FALLBACK_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn8n2UAAAAASUVORK5CYII="
)

IMAGE_CACHE = {}
YOUTUBE_CACHE = {}
IMAGE_CACHE_VERSION = "photo-style-v4"

# Common aliases for labels that often fail in exact YouTube search.
YOUTUBE_LABEL_ALIASES = {
    "step-ups": ["step up", "step ups", "step-up exercise"],
    "push-ups": ["push up", "push ups", "push-up exercise"],
    "pull-ups": ["pull up", "pull ups", "pull-up exercise"],
}


def _normalize_exercise_name(ex_name: str) -> str:
    return " ".join(str(ex_name).strip().lower().split())


def _extract_exercise_label(raw_text: str) -> str:
    """
    Extract the clean exercise name from a RAG sentence like:
      "Push-up is a bodyweight exercise..."         -> "Push-up"
      "Squat is a compound lower body exercise..."  -> "Squat"
      "Bicep curl isolates the biceps..."           -> "Bicep curl"
      "Bulgarian split squat strengthens legs..."   -> "Bulgarian split squat"

    Strategy: the exercise name is everything BEFORE the first verb/connector.
    """
    raw = (raw_text or "").strip()
    # Split on the first occurrence of common verb patterns
    # Use a regex that matches " is ", " are ", " improve", " target", " strengthen",
    # " isolate", " combine", " use", " perform", ":" — all typical in this corpus
    verb_pattern = re.compile(
        r'\s+(is|are|improve[sd]?|target[sd]?|strengthen[sd]?|isolate[sd]?|'
        r'combine[sd]?|uses?|performs?|build[sd]?|develop[sd]?|work[sd]?)\b',
        re.IGNORECASE
    )
    m = verb_pattern.search(raw)
    if m:
        label = raw[:m.start()].strip()
        # Sanity-check: label should be short and not contain a full sentence
        if 1 < len(label) < 60:
            return label

    # Fallback: first word group before colon
    if ":" in raw:
        candidate = raw.split(":")[0].strip()
        if 1 < len(candidate) < 60:
            return candidate

    # Last fallback: first 4 words
    words = raw.split()
    return " ".join(words[:4]) if words else raw[:40]


def _youtube_embed_search_url(label: str) -> str:
    query = quote((label or "fitness exercise").strip())
    # Use a reliable web search URL as fallback; frontend can open this directly.
    return f"https://www.youtube.com/results?search_query={query}"


def _youtube_query_candidates(label: str):
    """Build progressively broader query candidates for a label."""
    base = (label or "").strip()
    if not base:
        return []

    normalized = re.sub(r"\s+", " ", base).strip()
    dashed_to_space = normalized.replace("-", " ")
    no_punct = re.sub(r"[^a-zA-Z0-9 ]", "", dashed_to_space).strip()

    candidates = [normalized, dashed_to_space, no_punct]

    # Add configured aliases for known problematic names.
    alias_key = normalized.lower()
    candidates.extend(YOUTUBE_LABEL_ALIASES.get(alias_key, []))

    # Deduplicate while preserving order.
    seen = set()
    unique = []
    for c in candidates:
        c = c.strip()
        if c and c.lower() not in seen:
            seen.add(c.lower())
            unique.append(c)
    return unique


def youtube_link_for(label: str) -> str:
    """
    Search YouTube for a tutorial video for the given clean exercise label.
    Falls back to an exercise-specific embed search URL when API key/search fails.
    """
    label = (label or "").strip()
    if not label:
        return YOUTUBE_FALLBACK

    cache_key = label.lower()
    if cache_key in YOUTUBE_CACHE:
        return YOUTUBE_CACHE[cache_key]

    if not YOUTUBE_KEY:
        result = _youtube_embed_search_url(label)
        YOUTUBE_CACHE[cache_key] = result
        return result

    url = "https://www.googleapis.com/youtube/v3/search"

    # Try several query variants before giving up.
    for candidate in _youtube_query_candidates(label):
        query = f"{candidate} exercise proper form tutorial"
        print(f"[YOUTUBE] searching: {query}")

        params = {
            "part": "snippet",
            "q": query,
            "key": YOUTUBE_KEY,
            "maxResults": 10,
            "type": "video",
            "videoEmbeddable": "true",
            "safeSearch": "moderate",
            "relevanceLanguage": "en",
        }

        try:
            res = requests.get(url, params=params, timeout=8).json()
        except Exception as e:
            print(f"[YOUTUBE] request failed: {e}")
            continue

        items = res.get("items", [])
        if not items:
            print(f"[YOUTUBE] no results for: {query}")
            continue

        # Rank by how many candidate words appear in title.
        candidate_words = set(re.sub(r"[^a-z0-9 ]", " ", candidate.lower()).split()) - {"the", "a", "an", "and", "to", "of", "for", "how", "exercise"}
        ranked = []
        for item in items:
            title = item.get("snippet", {}).get("title", "").lower()
            score = sum(1 for w in candidate_words if w in title)
            ranked.append((score, item))

        ranked.sort(key=lambda x: x[0], reverse=True)
        best_item = ranked[0][1]
        video_id = best_item.get("id", {}).get("videoId")

        if video_id:
            result = f"https://www.youtube.com/embed/{video_id}"
            print(f"[YOUTUBE] -> selected video_id={video_id}")
            YOUTUBE_CACHE[cache_key] = result
            return result

    # Final fallback remains exercise-specific.
    result = _youtube_embed_search_url(label)
    YOUTUBE_CACHE[cache_key] = result
    return result


def generate_exercise_image(ex_name: str) -> str:
    key = f"{IMAGE_CACHE_VERSION}:{_normalize_exercise_name(ex_name)}"
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]

    prompt = (
        f"Create a professional fitness demonstration photo for {ex_name}. "
        "Show the correct exercise form clearly with a real person, clean studio lighting, sharp focus, "
        "and a polished sports/fitness magazine look. No diagrams, no stick figures, no watermark, no clutter."
    )

    def _inline_from_response(response):
        candidates = getattr(response, "candidates", []) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", []) if content else []
            for part in parts:
                inline_data = getattr(part, "inline_data", None)
                if inline_data and getattr(inline_data, "data", None):
                    img_bytes = inline_data.data
                    encoded = base64.b64encode(img_bytes).decode("ascii")
                    return f"data:image/png;base64,{encoded}"
        return None

    def _photo_placeholder_data_url(label: str):
        safe_label = (label or "Exercise").replace("&", "and")[:28]
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='900' height='520'>"
            "<defs><linearGradient id='g' x1='0' x2='1' y1='0' y2='1'><stop offset='0%' stop-color='#0f172a'/><stop offset='100%' stop-color='#111827'/></linearGradient></defs>"
            "<rect width='100%' height='100%' fill='url(#g)'/>"
            "<rect x='24' y='24' width='852' height='472' rx='22' fill='#1f2937' stroke='#4ade80' stroke-width='2'/>"
            f"<text x='50%' y='225' text-anchor='middle' fill='#d1fae5' font-family='Arial' font-size='34' font-weight='700'>{safe_label}</text>"
            "<text x='50%' y='270' text-anchor='middle' fill='#93c5fd' font-family='Arial' font-size='18'>Photo generation unavailable</text>"
            "<text x='50%' y='306' text-anchor='middle' fill='#86efac' font-family='Arial' font-size='16'>Using a clean fallback card</text>"
            "</svg>"
        )
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    def _search_pexels_image_url(term: str):
        if not PEXELS_API_KEY:
            return None
        try:
            response = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": f"{term} fitness exercise", "per_page": 1, "orientation": "landscape"},
                timeout=10,
            )
            if not response.ok:
                return None
            photos = response.json().get("photos", [])
            if not photos:
                return None
            src = photos[0].get("src", {})
            return src.get("large2x") or src.get("large") or src.get("medium") or src.get("original")
        except Exception:
            return None

    def _generate_gemini_exercise_image():
        if not client_llm or not USE_AI_EXERCISE_IMAGES:
            return None

        # Prefer native image-generation APIs when the SDK exposes them.
        try:
            if hasattr(client_llm.models, "generate_images"):
                image_result = client_llm.models.generate_images(model=GEMINI_IMAGE_MODEL, prompt=prompt)
                generated_images = getattr(image_result, "generated_images", []) or []
                for img in generated_images:
                    image_obj = getattr(img, "image", None)
                    img_bytes = getattr(image_obj, "image_bytes", None) if image_obj else None
                    if img_bytes:
                        encoded = base64.b64encode(img_bytes).decode("ascii")
                        return f"data:image/png;base64,{encoded}"
        except Exception as e:
            print(f"[IMAGE] generate_images failed for {GEMINI_IMAGE_MODEL}: {e}")

        # Some SDK versions may surface image payloads through generate_content.
        try:
            response = client_llm.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
            )
            inline_image = _inline_from_response(response)
            if inline_image:
                return inline_image
        except Exception as e:
            print(f"[IMAGE] generate_content failed for {GEMINI_IMAGE_MODEL}: {e}")

        return None

    ai_image = _generate_gemini_exercise_image()
    if ai_image:
        IMAGE_CACHE[key] = ai_image
        return ai_image

    # Photo fallback first, then a neutral card if no image source is available.
    pexels_url = _search_pexels_image_url(ex_name)
    if pexels_url:
        IMAGE_CACHE[key] = pexels_url
        return pexels_url

    placeholder = _photo_placeholder_data_url(ex_name)
    IMAGE_CACHE[key] = placeholder
    return placeholder

# ==========================
# LOAD DATA FROM POSTGRES → CHROMA
# ==========================
def load_data_to_chroma():
    conn = psycopg2.connect(
        dbname="fitness_rag",
        user="postgres",
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()

    cursor.execute("SELECT id, content FROM documents;")
    rows = cursor.fetchall()

    texts = [r[1] for r in rows]
    ids = [str(r[0]) for r in rows]

    if not texts:
        return

    embeddings = model.encode(texts).tolist()

    existing_ids = set()
    try:
        existing_ids = set(collection.get()["ids"])
    except:
        pass

    new_texts, new_ids, new_embeddings = [], [], []

    for t, i, e in zip(texts, ids, embeddings):
        if i not in existing_ids:
            new_texts.append(t)
            new_ids.append(i)
            new_embeddings.append(e)

    if new_texts:
        collection.add(
            documents=new_texts,
            embeddings=new_embeddings,
            ids=new_ids
        )

    cursor.close()
    conn.close()

# Fail fast if encrypted health data exists but the key to read it is missing.
_assert_health_data_key_present_if_needed()

# load once on startup
load_data_to_chroma()

# ==========================
# REQUEST MODEL
# ==========================
class Query(BaseModel):
    question: str

# ==========================
# LANGUAGE DETECTION
# ==========================
def is_mk(text: str) -> bool:
    mk_chars = "ѓжчќшљњџабвгдезијклмнопрстуфхцчџш"
    return any(ch in text.lower() for ch in mk_chars)


def is_plan_request(text: str) -> bool:
    t = text.lower()
    keywords = ["plan", "workout plan", "7-day", "седум", "план", "неделен план"]
    return any(k in t for k in keywords)

# ==========================
# SAFE GEMINI TEXT
# ==========================
def extract_text(resp):
    try:
        if hasattr(resp, "text") and resp.text:
            return resp.text

        if hasattr(resp, "candidates") and resp.candidates:
            cand = resp.candidates[0]
            if hasattr(cand, "content") and cand.content.parts:
                parts = []
                for part in cand.content.parts:
                    if getattr(part, "text", None):
                        parts.append(part.text)
                if parts:
                    return "\n".join(parts)
    except Exception as e:
        print("EXTRACT ERROR:", e)

    return None



# ==========================
# GENERIC FALLBACK
# ==========================
def general_fallback(question):
    if is_mk(question):
        return """
SHORT ANSWER:
За добро здравје вежбај редовно и јади балансирана исхрана.

FULL PLAN:
Комбинирај кардио (трчање, јаже, брзо одење) и силов тренинг 3-4 пати неделно.
Спиј доволно и внесувај протеини и вода.
"""
    else:
        return """
SHORT ANSWER:
Exercise regularly and maintain a balanced diet.

FULL PLAN:
Combine cardio (running, jump rope, walking) with strength training 3-4 times per week.
Sleep well, stay hydrated and eat enough protein.
"""


def _generate_text_with_retry(prompt: str, image_parts: list | None = None):
    """image_parts, when given, is a list of {"inline_data": {"mime_type", "data"}}
    dicts appended after the text part, for multimodal (vision) calls — e.g.
    blood-test image analysis. Existing callers are unaffected (defaults to
    text-only)."""
    if not client_llm:
        return None, "Gemini API key is missing"

    parts = [{"text": prompt}]
    if image_parts:
        parts.extend(image_parts)

    last_error = ""
    for attempt in range(GEMINI_MAX_RETRIES + 1):
        try:
            resp = client_llm.models.generate_content(
                model=GEMINI_TEXT_MODEL,
                contents=[{"role": "user", "parts": parts}],
            )
            text = extract_text(resp)
            if text:
                return text, ""
            last_error = "Empty AI response"
        except Exception as e:
            last_error = str(e)
            upper = last_error.upper()
            retryable = any(token in upper for token in ["503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE"])
            print(f"[GEMINI] attempt={attempt + 1} failed: {last_error}")
            if retryable and attempt < GEMINI_MAX_RETRIES:
                time.sleep(1 + attempt)
                continue
            break

    return None, last_error or "AI request failed"

# ==========================
# ROOT
# ==========================
@app.get("/")
def home():
    return {"message": "Fitness RAG API is running!"}

@app.get("/ping")
def ping():
    return {"ok": True}

# ==========================
# EXERCISE NAME EXTRACTION
# ==========================
def extract_exercise_name(text: str) -> str:
    t = text.lower()

    if "step" in t: return "step ups"
    if "push" in t: return "push ups"
    if "squat" in t: return "squats"
    if "plank" in t: return "plank"
    if "lunge" in t: return "lunges"
    if "burpee" in t: return "burpees"
    if "crunch" in t or "abs" in t: return "abs"
    if "deadlift" in t: return "deadlift"
    if "pull" in t: return "pull ups"
    if "bench" in t: return "bench press"

    return text


def dedupe_documents(documents):
    cleaned = []
    seen = set()

    for doc in documents:
        normalized = str(doc).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    return cleaned


def select_recommended_documents(documents, distances, limit=EXERCISE_RECOMMENDATION_LIMIT):
    relevant_docs = []
    fallback_docs = []
    seen = set()

    for doc, dist in zip(documents, distances):
        normalized = str(doc).strip()
        if not normalized or normalized in seen:
            continue

        seen.add(normalized)
        if dist < DISTANCE_THRESHOLD and len(relevant_docs) < limit:
            relevant_docs.append(normalized)
        fallback_docs.append(normalized)

    if len(relevant_docs) >= limit:
        return relevant_docs[:limit]

    for doc in fallback_docs:
        if doc not in relevant_docs:
            relevant_docs.append(doc)
        if len(relevant_docs) >= limit:
            break

    return relevant_docs[:limit]


def _retrieval_diagnostics(documents, distances, selected, limit=None) -> dict:
    """Counts how many candidates actually passed DISTANCE_THRESHOLD versus
    how many were back-filled below it by select_recommended_documents, so a
    calibration study can measure what a binding threshold would cost.
    Read-only — does not change select_recommended_documents' behavior."""
    if limit is None:
        limit = EXERCISE_RECOMMENDATION_LIMIT

    passed = sum(1 for d in distances if d < DISTANCE_THRESHOLD)
    returned = len(selected)
    backfilled = max(0, returned - min(passed, limit))

    diag = {
        "vector_search_results": len(documents),
        "distance_threshold": DISTANCE_THRESHOLD,
        "limit": limit,
        "passed_threshold_count": passed,
        "returned_count": returned,
        "backfill_count": backfilled,
    }
    print(
        f"[RETRIEVAL] candidates={diag['vector_search_results']} "
        f"passed_threshold={passed} returned={returned} backfilled={backfilled} "
        f"(threshold={DISTANCE_THRESHOLD})"
    )
    return diag


# Mifflin-St Jeor activity multiplier assumption. The task doesn't ask for a
# per-user activity-level UI, so we document a single fixed "lightly active"
# PAL here rather than guessing at one. See CHANGES_FOR_PAPER.md.
BMR_ACTIVITY_MULTIPLIER = 1.375


def compute_bmr_tdee(height_cm, weight_kg, age, gender):
    """Mifflin-St Jeor BMR + TDEE. Returns (None, None) if any input is missing.
    s = +5 (male) / -161 (female); gender="other"/unrecognized uses the
    arithmetic midpoint (-78) as a documented, non-clinical approximation —
    Mifflin-St Jeor has no validated non-binary term in the literature."""
    if not height_cm or not weight_kg or not age or not gender:
        return None, None

    try:
        height_cm = float(height_cm)
        weight_kg = float(weight_kg)
        age = float(age)
    except (TypeError, ValueError):
        return None, None

    s = {"male": 5, "female": -161}.get(str(gender).strip().lower(), -78)
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + s
    tdee = bmr * BMR_ACTIVITY_MULTIPLIER
    return round(bmr, 1), round(tdee, 1)


def build_prefs_block(user: dict | None) -> str:
    """Compact natural-language block summarizing a user's stored preferences,
    for splicing into generation prompts only. Returns "" when there is no user
    or no preferences set. Must NEVER be passed to the embedding model — prompts
    only (see the CONTRACT comment above the model.encode(...) call in /ask)."""
    if not user:
        return ""

    prefs = user.get("preferences", {}) or {}
    lines = []

    goal = prefs.get("goal")
    if goal:
        lines.append(f"- Goal: {goal}")

    gender = prefs.get("gender")
    age = prefs.get("age")
    if gender or age:
        who = " ".join(filter(None, [f"{age}-year-old" if age else "", gender or ""])).strip()
        if who:
            lines.append(f"- User: {who}")

    height_cm = prefs.get("height_cm")
    weight_kg = prefs.get("weight_kg")
    if height_cm:
        lines.append(f"- Height: {height_cm} cm")
    if weight_kg:
        lines.append(f"- Weight: {weight_kg} kg")

    bmr, tdee = compute_bmr_tdee(height_cm, weight_kg, age, gender)
    if bmr is not None and tdee is not None:
        lines.append(f"- Estimated BMR: {bmr} kcal/day, TDEE: {tdee} kcal/day (Mifflin-St Jeor)")

    if prefs.get("bloodTestImage"):
        lines.append("- User has provided a blood test panel image (not decoded here).")

    if not lines:
        return ""

    return "User profile (use to personalize advice, do not repeat back verbatim):\n" + "\n".join(lines)


# MAIN ENDPOINT
# ==========================
@app.post("/ask")
def ask(q: Query, user: dict | None = Depends(optional_user)):
    try:
        # CONTRACT: model.encode receives ONLY the raw question string — never
        # interpolate preferences/context here. This separation is a claimed
        # contribution of the paper (all-MiniLM-L6-v2 truncates at 256
        # word-pieces) and is regression-tested in test_app.py.
        # 1️⃣ embed question
        query_embedding = model.encode([q.question]).tolist()

        # Preferences are for the GENERATION prompts only (below), never for
        # retrieval — built here, spliced into prompt text, kept far from
        # anything passed to the encoder.
        prefs_block = build_prefs_block(user)

        # 2️⃣ vector search with scores
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=VECTOR_SEARCH_RESULTS,
            include=["documents", "distances"]
        )

        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        # 3️⃣ filter relevant docs and keep up to 8 unique recommendations
        raw_docs, raw_distances = docs, distances
        docs = select_recommended_documents(docs, distances)
        retrieval_diag = _retrieval_diagnostics(raw_docs, raw_distances, docs)
        # 4️⃣ decide if we use context
        use_context = len(docs) > 0

        if use_context:
            context = " ".join(docs)
            context_block = f"Context:\n{context}"
        else:
            context_block = "No specific exercise context available."

        if is_plan_request(q.question):

            conn = psycopg2.connect(
                dbname="fitness_rag",
                user="postgres",
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cursor = conn.cursor()

            cursor.execute("SELECT content FROM documents")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            all_exercises = list(set([r[0] for r in rows]))

            if len(all_exercises) < 16:
                return {"answer": "Not enough exercises in database."}

            selected = random.sample(all_exercises, 16)

            allowed_exercises = "\n".join(selected)

            lang = "Macedonian" if is_mk(q.question) else "English"

            plan_prompt = f"""
        You are a certified personal trainer.

        You MUST build a 7-day workout plan using ONLY the exercises listed below.

        ALLOWED EXERCISES:
        {allowed_exercises}

        {prefs_block}

        User request:
        {q.question}

        Rules:
        - Use ONLY exercises from the allowed list
        - Do not repeat the same exercise on multiple days
        - Create Day 1 to Day 7
        - Include sets and reps
        - Include rest days
        - Answer ONLY in {lang}
        """

            resp = client_llm.models.generate_content(
                model="gemini-2.5-flash",
                contents=[{
                    "role": "user",
                    "parts": [{"text": plan_prompt}]
                }]
            )

            answer = extract_text(resp)

            return {
                "question": q.question,
                "type": "hybrid_database_plan",
                "answer": answer,
                "personalized": bool(user),
            }

        # 5️⃣ prompt
        lang = "Macedonian" if is_mk(q.question) else "English"
        prompt = f"""
You are a certified professional fitness coach.

{context_block}

{prefs_block}

Question:
{q.question}

Instructions:
- Answer ONLY in {lang}
- Do NOT use any other language
- If context exists, use it; otherwise use general fitness knowledge
- You MUST structure your response with EXACTLY these two labeled sections (no bold, no markdown on the labels):

SHORT ANSWER:
[Write exactly 2-3 sentences summarising the core advice]

FULL PLAN:
[Write detailed advice, tips, steps, or a training plan here]
"""

        # 6️⃣ Gemini
        try:
            resp = client_llm.models.generate_content(
                model="gemini-2.5-flash",
                contents=[{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            )

            answer = extract_text(resp)

            if not answer:
                answer = general_fallback(q.question)

        except:
            answer = general_fallback(q.question)

        structured_exercises = []

        for d in docs:
            # Extract clean label (e.g. "Bicep curl") for image + YouTube search
            label = _extract_exercise_label(d)
            print(f"[DEBUG] raw='{d[:60]}' -> label='{label}'")

            structured_exercises.append({
                "name": d,          # FULL sentence shown on card
                "label": label,     # clean name for image/video lookups
                "video": youtube_link_for(label),   # pass label directly, not raw
                "images": [generate_exercise_image(label)],
                "raw": d,
            })

        return {
            "question": q.question,
            "answer": answer,
            "exercises": structured_exercises,
            "personalized": bool(user),
            "retrieval": retrieval_diag,
        }

    except Exception as e:
        return {"error": str(e)}


def _run_retrieval_for_chat(question: str, user: dict | None):
    """Same retrieval steps as /ask's chat branch above (embed -> vector
    search -> select_recommended_documents -> diagnostics -> context_block),
    factored out so /ask/stream (below) can reuse them without touching
    /ask's already-verified body. CONTRACT: model.encode receives ONLY the
    raw question — same guarantee as /ask, regression-tested in
    test_app.py."""
    query_embedding = model.encode([question]).tolist()
    prefs_block = build_prefs_block(user)

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=VECTOR_SEARCH_RESULTS,
        include=["documents", "distances"],
    )
    raw_docs = results.get("documents", [[]])[0]
    raw_distances = results.get("distances", [[]])[0]
    docs = select_recommended_documents(raw_docs, raw_distances)
    retrieval_diag = _retrieval_diagnostics(raw_docs, raw_distances, docs)

    if docs:
        context_block = "Context:\n" + " ".join(docs)
    else:
        context_block = "No specific exercise context available."

    return docs, prefs_block, context_block, retrieval_diag


def _build_structured_exercises(docs):
    """Same exercise-card assembly as /ask's chat branch, factored out for
    reuse by /ask/stream."""
    structured_exercises = []
    for d in docs:
        label = _extract_exercise_label(d)
        structured_exercises.append({
            "name": d,
            "label": label,
            "video": youtube_link_for(label),
            "images": [generate_exercise_image(label)],
            "raw": d,
        })
    return structured_exercises


@app.post("/ask/stream")
def ask_stream(q: Query, user: dict | None = Depends(optional_user)):
    """SSE variant of /ask's chat branch. Streams generated text as it
    arrives via Gemini's generate_content_stream, then a final event
    carrying the exercise cards (delivered after the text stream, as today's
    non-streaming /ask does) plus retrieval diagnostics. Retrieval itself is
    NOT streamed — it runs synchronously up front, reusing the exact same
    path as /ask's chat branch. On any generation failure, yields a single
    error event instead of raising mid-stream or leaving the connection
    hanging; the frontend falls back to the non-streaming /ask in that case."""
    docs, prefs_block, context_block, retrieval_diag = _run_retrieval_for_chat(q.question, user)
    lang = "Macedonian" if is_mk(q.question) else "English"
    prompt = f"""
You are a certified professional fitness coach.

{context_block}

{prefs_block}

Question:
{q.question}

Instructions:
- Answer ONLY in {lang}
- Do NOT use any other language
- If context exists, use it; otherwise use general fitness knowledge
- You MUST structure your response with EXACTLY these two labeled sections (no bold, no markdown on the labels):

SHORT ANSWER:
[Write exactly 2-3 sentences summarising the core advice]

FULL PLAN:
[Write detailed advice, tips, steps, or a training plan here]
"""

    def event_gen():
        try:
            if not client_llm:
                raise RuntimeError("Gemini API key is not configured on the server.")
            stream = client_llm.models.generate_content_stream(
                model=GEMINI_TEXT_MODEL,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
            )
            for chunk in stream:
                text = extract_text(chunk)
                if text:
                    yield f"data: {json.dumps({'delta': text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            return

        exercises = _build_structured_exercises(docs)
        yield (
            "data: "
            + json.dumps({
                "done": True,
                "exercises": exercises,
                "retrieval": retrieval_diag,
                "personalized": bool(user),
            })
            + "\n\n"
        )

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/exercise-assets")
def exercise_assets(text: str):
    """Return best-effort label/image/video for a saved exercise entry."""
    label = _extract_exercise_label(text)
    return {
        "label": label,
        "image": generate_exercise_image(label),
        "video": youtube_link_for(label),
    }


from fastapi.responses import FileResponse

@app.get("/download/{filename}")
def download_file(filename: str):
    path = f"plans/{filename}"
    media_type = "application/pdf" if filename.lower().endswith(".pdf") else "text/plain"
    return FileResponse(path, media_type=media_type, filename=filename)


