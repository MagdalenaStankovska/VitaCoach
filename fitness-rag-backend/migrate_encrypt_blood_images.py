"""One-off migration: encrypts any plaintext bloodTestImage values in
data/users.json in place, using Fernet + HEALTH_DATA_KEY (see app.py's
encrypt_blood_image for the same logic — duplicated here deliberately rather
than imported, so running this script doesn't trigger app.py's full startup
sequence, i.e. the SentenceTransformer load and the Postgres connection,
just to rewrite a JSON file).

Usage (run from fitness-rag-backend/, with HEALTH_DATA_KEY set in the
environment or .env):
    python migrate_encrypt_blood_images.py

Backs up data/users.json to data/users.json.bak before writing anything,
matching the .bak convention already used elsewhere in this repo. Refuses to
run without HEALTH_DATA_KEY set.
"""
import json
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from cryptography.fernet import Fernet  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "data" / "users.json"


def _looks_encrypted(value: str) -> bool:
    return bool(value) and not value.startswith("data:")


def main() -> int:
    health_data_key = os.getenv("HEALTH_DATA_KEY", "")
    if not health_data_key:
        print("ERROR: HEALTH_DATA_KEY is not set. Generate one with:")
        print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
        print("then set it in your environment or .env before running this migration.")
        return 1

    fernet = Fernet(health_data_key.encode())

    if not USERS_FILE.exists():
        print(f"No users file at {USERS_FILE} — nothing to migrate.")
        return 0

    users = json.loads(USERS_FILE.read_text(encoding="utf-8"))

    backup_path = USERS_FILE.with_suffix(USERS_FILE.suffix + ".bak")
    shutil.copy2(USERS_FILE, backup_path)
    print(f"Backed up {USERS_FILE} -> {backup_path}")

    scanned = 0
    encrypted = 0
    already_encrypted = 0

    for user in users:
        prefs = user.get("preferences") or {}
        blood_img = prefs.get("bloodTestImage")
        if not blood_img:
            continue
        scanned += 1
        if _looks_encrypted(blood_img):
            already_encrypted += 1
            continue
        prefs["bloodTestImage"] = fernet.encrypt(blood_img.encode()).decode()
        user["preferences"] = prefs
        encrypted += 1

    tmp_path = USERS_FILE.with_suffix(USERS_FILE.suffix + ".tmp")
    tmp_path.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(USERS_FILE)

    print(f"{scanned} users scanned, {encrypted} images encrypted, {already_encrypted} already-encrypted skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
