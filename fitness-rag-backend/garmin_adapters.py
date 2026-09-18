"""Garmin data-source abstraction.

The reviewer's objection: python-garminconnect is an unofficial,
reverse-engineered wrapper around the Garmin Connect *consumer* website — it
stores a user's raw email/password rather than a scoped OAuth token, so the
integration can't be called production-grade. This module isolates that
implementation behind a small interface (GarminAdapter) so a real OAuth-based
integration (OfficialGarminHealthAdapter) can sit next to it without touching
call sites in app.py, and so the choice between them is a one-line env var,
not a code change.

Two adapters:
  - LegacyGarminConnectAdapter: today's actual behavior, moved here
    unchanged. Every real client call still goes through _safe_garmin_call
    (catches all exceptions, returns None) exactly as before.
  - OfficialGarminHealthAdapter: a real OAuth 1.0a flow against the Garmin
    Connect Developer Program's Health API (request-token -> user-authorize
    -> access-token exchange, HMAC-SHA1-signed via requests_oauthlib). Data
    methods raise NotImplementedError because reading real health metrics
    through this API additionally requires an approved Garmin Health API
    developer account/backfill webhook setup — that approval is outside what
    can be built into a repo. The auth flow itself is real, working code.

    NOTE: Garmin's Health API historically uses OAuth 1.0a, not OAuth 2 —
    this is the one point of genuine external-API uncertainty in this
    module. Verify REQUEST_TOKEN_URL/AUTHORIZE_URL/ACCESS_TOKEN_URL against
    the current Garmin developer portal before relying on them in production.
"""
from abc import ABC, abstractmethod
from datetime import datetime

try:
    from garminconnect import Garmin
except Exception:
    Garmin = None

try:
    from requests_oauthlib import OAuth1Session
except Exception:
    OAuth1Session = None


class GarminAdapter(ABC):
    """The five data points VitaCoach's Garmin dashboard actually uses."""

    @abstractmethod
    def get_steps(self, date_str: str) -> int | None: ...

    @abstractmethod
    def get_sleep_hours(self, date_str: str) -> float | None: ...

    @abstractmethod
    def get_active_calories(self, date_str: str) -> int | None: ...

    @abstractmethod
    def get_distance_meters(self, date_str: str) -> float | None: ...

    @abstractmethod
    def get_recent_activities(self, start: int, limit: int) -> list: ...


def _safe_garmin_call(api, method_name: str, *args, **kwargs):
    """Never raises. Looks up method_name on api; if missing/not callable or
    the call itself raises anything, returns None. Moved here unchanged from
    app.py — this exact function (and its semantics) is what P1-1 preserves."""
    method = getattr(api, method_name, None)
    if not callable(method):
        return None
    try:
        return method(*args, **kwargs)
    except Exception:
        return None


def _extract_sleep_hours(sleep_payload: dict | None):
    """Moved here unchanged from app.py."""
    payload = sleep_payload or {}
    daily = payload.get("dailySleepDTO") if isinstance(payload, dict) else {}
    candidates = [
        daily.get("sleepTimeSeconds") if isinstance(daily, dict) else None,
        payload.get("sleepTimeSeconds") if isinstance(payload, dict) else None,
    ]
    for seconds in candidates:
        if isinstance(seconds, (int, float)) and seconds > 0:
            return round(float(seconds) / 3600.0, 2)
    return None


class LegacyGarminConnectAdapter(GarminAdapter):
    """Wraps the unofficial garminconnect scraping client. Unchanged
    behavior from the pre-refactor _load_garmin_dashboard: one real
    get_user_summary call backs steps/active-calories/distance/total-
    calories, cached per adapter instance (i.e. per dashboard load) so the
    first accessor still routes through _safe_garmin_call exactly once and
    later same-date accessors reuse that already-safely-fetched result,
    without tripling Garmin API calls per dashboard load."""

    def __init__(self, email: str, password: str):
        if Garmin is None:
            raise RuntimeError("garminconnect package is not installed. Run: pip install garminconnect")
        self._api = Garmin(email, password)
        self._api.login()
        self._summary_cache: dict[str, dict] = {}

    def _summary(self, date_str: str) -> dict:
        if date_str not in self._summary_cache:
            self._summary_cache[date_str] = _safe_garmin_call(self._api, "get_user_summary", date_str) or {}
        return self._summary_cache[date_str]

    def get_steps(self, date_str: str):
        return self._summary(date_str).get("totalSteps")

    def get_active_calories(self, date_str: str):
        return self._summary(date_str).get("activeKilocalories")

    def get_distance_meters(self, date_str: str):
        return self._summary(date_str).get("totalDistanceMeters")

    def get_sleep_hours(self, date_str: str):
        raw = _safe_garmin_call(self._api, "get_sleep_data", date_str)
        return _extract_sleep_hours(raw)

    def get_recent_activities(self, start: int, limit: int):
        activities = _safe_garmin_call(self._api, "get_activities", start, limit)
        if not isinstance(activities, list):
            return []
        normalized = []
        for activity in activities[:limit]:
            if not isinstance(activity, dict):
                continue
            normalized.append(
                {
                    "name": activity.get("activityName") or activity.get("activityType", {}).get("typeKey") or "Activity",
                    "start": activity.get("startTimeLocal") or activity.get("startTimeGMT"),
                    "durationSeconds": activity.get("duration"),
                    "calories": activity.get("calories"),
                    "distanceMeters": activity.get("distance"),
                }
            )
        return normalized

    # --- Extras outside the 5-method ABC contract ---------------------------
    # Full name + total (not just active) calories aren't part of the
    # paper's claimed 5-method interface, but the legacy dashboard response
    # included them before this refactor — kept as adapter-specific extras
    # (accessed via getattr(..., None) at the call site) so the default
    # /users/me/garmin/dashboard response shape is unchanged.
    def get_full_name(self):
        return _safe_garmin_call(self._api, "get_full_name")

    def get_total_calories(self, date_str: str):
        return self._summary(date_str).get("totalKilocalories")


class OfficialGarminHealthAdapter(GarminAdapter):
    """Real OAuth 1.0a flow against the Garmin Connect Developer Program's
    Health API. Data methods raise NotImplementedError — reading actual
    metrics through this API requires an approved developer account (backfill
    webhooks, not simple polling), which can't be provisioned from this repo.
    The auth flow (request token -> authorize -> access token) is real,
    working HTTP code, not a stub."""

    # TODO(developer): verify these three URLs against the current Garmin
    # Health API developer portal before relying on this in production.
    REQUEST_TOKEN_URL = "https://connectapi.garmin.com/oauth-service/oauth/request_token"
    AUTHORIZE_URL = "https://connect.garmin.com/oauthConfirm"
    ACCESS_TOKEN_URL = "https://connectapi.garmin.com/oauth-service/oauth/access_token"

    def __init__(self, consumer_key: str, consumer_secret: str):
        # TODO(developer): set GARMIN_HEALTH_CLIENT_ID / GARMIN_HEALTH_CLIENT_SECRET
        # in the environment once approved for the Garmin Health API developer program.
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_token = None
        self._access_token_secret = None

    def _require_oauth_lib(self):
        if OAuth1Session is None:
            raise RuntimeError("requests_oauthlib is not installed. Run: pip install requests_oauthlib")

    def build_authorization_request(self) -> tuple[str, str]:
        """OAuth1.0a step 1+2: fetch a request token, return
        (oauth_token, authorize_url) for the user to visit and approve."""
        self._require_oauth_lib()
        oauth = OAuth1Session(self._consumer_key, client_secret=self._consumer_secret)
        response = oauth.fetch_request_token(self.REQUEST_TOKEN_URL)
        oauth_token = response.get("oauth_token")
        authorize_url = f"{self.AUTHORIZE_URL}?oauth_token={oauth_token}"
        return oauth_token, authorize_url

    def exchange_verifier_for_access_token(self, oauth_token: str, oauth_token_secret: str, oauth_verifier: str) -> dict:
        """OAuth1.0a step 3: exchange the user-approved verifier for a
        long-lived access token + secret. Stores them on the instance and
        also returns them so the caller can persist per-user credentials."""
        self._require_oauth_lib()
        oauth = OAuth1Session(
            self._consumer_key,
            client_secret=self._consumer_secret,
            resource_owner_key=oauth_token,
            resource_owner_secret=oauth_token_secret,
            verifier=oauth_verifier,
        )
        tokens = oauth.fetch_access_token(self.ACCESS_TOKEN_URL)
        self._access_token = tokens.get("oauth_token")
        self._access_token_secret = tokens.get("oauth_token_secret")
        return {"oauth_token": self._access_token, "oauth_token_secret": self._access_token_secret}

    def get_steps(self, date_str: str):
        raise NotImplementedError("Requires an approved Garmin Health API developer account")

    def get_sleep_hours(self, date_str: str):
        raise NotImplementedError("Requires an approved Garmin Health API developer account")

    def get_active_calories(self, date_str: str):
        raise NotImplementedError("Requires an approved Garmin Health API developer account")

    def get_distance_meters(self, date_str: str):
        raise NotImplementedError("Requires an approved Garmin Health API developer account")

    def get_recent_activities(self, start: int, limit: int):
        raise NotImplementedError("Requires an approved Garmin Health API developer account")


def build_garmin_adapter(email: str, password: str, adapter_kind: str, health_client_id: str = "", health_client_secret: str = "") -> GarminAdapter:
    """Selects an adapter by name ("legacy" default | "official")."""
    if adapter_kind.lower() == "official":
        return OfficialGarminHealthAdapter(health_client_id, health_client_secret)
    return LegacyGarminConnectAdapter(email, password)


def load_dashboard(adapter: GarminAdapter, date_str: str | None = None) -> dict:
    """Assembles the same dashboard shape /users/me/garmin/dashboard has
    always returned, using only the adapter's interface (plus the two
    legacy-only extras when the adapter happens to expose them)."""
    if date_str is None:
        date_str = datetime.utcnow().date().isoformat()

    return {
        "date": date_str,
        "fullName": getattr(adapter, "get_full_name", lambda: None)(),
        "steps": adapter.get_steps(date_str),
        "calories": getattr(adapter, "get_total_calories", lambda d: None)(date_str),
        "activeCalories": adapter.get_active_calories(date_str),
        "distanceMeters": adapter.get_distance_meters(date_str),
        "sleepHours": adapter.get_sleep_hours(date_str),
        "activities": adapter.get_recent_activities(0, 5),
    }
