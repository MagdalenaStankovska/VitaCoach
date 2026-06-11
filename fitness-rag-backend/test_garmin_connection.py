from datetime import date
import os

from dotenv import load_dotenv

try:
    from garminconnect import Garmin
except Exception as exc:
    raise SystemExit(
        "garminconnect package is missing. Install with: pip install garminconnect"
    ) from exc


load_dotenv()

EMAIL = (os.getenv("GARMIN_EMAIL") or "").strip()
PASSWORD = os.getenv("GARMIN_PASSWORD") or ""

if not EMAIL or not PASSWORD:
    raise SystemExit("Missing GARMIN_EMAIL or GARMIN_PASSWORD in .env")


today = date.today().isoformat()

try:
    api = Garmin(EMAIL, PASSWORD)
    api.login()

    print("Connected successfully!")
    print("User:", api.get_full_name())

    summary = api.get_user_summary(today) or {}
    print("Date:", today)
    print("Steps:", summary.get("totalSteps"))
    print("Calories:", summary.get("totalKilocalories"))
except Exception as exc:
    print("Error:", exc)

