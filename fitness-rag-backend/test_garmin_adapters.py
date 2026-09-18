"""Unit tests for garmin_adapters.py. Deliberately does NOT import app.py —
these are fast, isolated tests against the adapter module alone."""
import garmin_adapters as ga


class _FakeGarminClient:
    """Stands in for garminconnect.Garmin — records call counts so tests can
    prove the summary-fetch caching behavior."""

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.summary_calls = 0
        self.logged_in = False

    def login(self):
        self.logged_in = True

    def get_user_summary(self, date_str):
        self.summary_calls += 1
        return {"totalSteps": 5000, "activeKilocalories": 300, "totalDistanceMeters": 4000.0, "totalKilocalories": 2100}

    def get_sleep_data(self, date_str):
        return {"dailySleepDTO": {"sleepTimeSeconds": 7 * 3600}}

    def get_activities(self, start, limit):
        return [{"activityName": "Run", "duration": 1800, "calories": 250, "distance": 5000}]

    def get_full_name(self):
        return "Test User"


def test_safe_garmin_call_never_raises():
    class Boom:
        def method(self):
            raise RuntimeError("network exploded")

    assert ga._safe_garmin_call(Boom(), "method") is None
    assert ga._safe_garmin_call(Boom(), "missing_method") is None


def test_extract_sleep_hours_variants():
    assert ga._extract_sleep_hours({"dailySleepDTO": {"sleepTimeSeconds": 3600 * 6.5}}) == 6.5
    assert ga._extract_sleep_hours({"sleepTimeSeconds": 3600 * 8}) == 8.0
    assert ga._extract_sleep_hours(None) is None
    assert ga._extract_sleep_hours({}) is None


def test_legacy_adapter_summary_cache_backs_three_methods(monkeypatch):
    monkeypatch.setattr(ga, "Garmin", _FakeGarminClient)
    adapter = ga.LegacyGarminConnectAdapter("a@b.com", "pw")
    date_str = "2026-01-01"

    steps = adapter.get_steps(date_str)
    active_cal = adapter.get_active_calories(date_str)
    distance = adapter.get_distance_meters(date_str)

    assert steps == 5000
    assert active_cal == 300
    assert distance == 4000.0
    # The three summary-derived methods share one real get_user_summary call,
    # cached per adapter instance — not tripled.
    assert adapter._api.summary_calls == 1

    assert adapter.get_sleep_hours(date_str) == 7.0
    activities = adapter.get_recent_activities(0, 5)
    assert len(activities) == 1
    assert activities[0]["name"] == "Run"
    assert adapter.get_full_name() == "Test User"
    assert adapter.get_total_calories(date_str) == 2100
    assert adapter._api.summary_calls == 1  # still cached


def test_official_adapter_data_methods_raise_not_implemented():
    adapter = ga.OfficialGarminHealthAdapter("consumer_key", "consumer_secret")
    for method_name, args in [
        ("get_steps", ("2026-01-01",)),
        ("get_sleep_hours", ("2026-01-01",)),
        ("get_active_calories", ("2026-01-01",)),
        ("get_distance_meters", ("2026-01-01",)),
        ("get_recent_activities", (0, 5)),
    ]:
        try:
            getattr(adapter, method_name)(*args)
            assert False, f"{method_name} should have raised NotImplementedError"
        except NotImplementedError:
            pass


def test_build_garmin_adapter_selects_by_env_var(monkeypatch):
    monkeypatch.setattr(ga, "Garmin", _FakeGarminClient)
    legacy = ga.build_garmin_adapter("a@b.com", "pw", "legacy")
    assert isinstance(legacy, ga.LegacyGarminConnectAdapter)

    official = ga.build_garmin_adapter("a@b.com", "pw", "official", "ck", "cs")
    assert isinstance(official, ga.OfficialGarminHealthAdapter)

    # default kind string not recognized falls back to legacy
    fallback = ga.build_garmin_adapter("a@b.com", "pw", "something-else")
    assert isinstance(fallback, ga.LegacyGarminConnectAdapter)


def test_load_dashboard_shape(monkeypatch):
    monkeypatch.setattr(ga, "Garmin", _FakeGarminClient)
    adapter = ga.LegacyGarminConnectAdapter("a@b.com", "pw")
    dashboard = ga.load_dashboard(adapter, "2026-01-01")
    assert dashboard == {
        "date": "2026-01-01",
        "fullName": "Test User",
        "steps": 5000,
        "calories": 2100,
        "activeCalories": 300,
        "distanceMeters": 4000.0,
        "sleepHours": 7.0,
        "activities": [
            {"name": "Run", "start": None, "durationSeconds": 1800, "calories": 250, "distanceMeters": 5000}
        ],
    }
