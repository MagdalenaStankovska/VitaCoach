import requests
import json

BASE = "https://korpa.mk"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://korpa.mk/",
    "Origin": "https://korpa.mk"
}

restaurants = [
    "junk-food",
    "balance-bistro",
    "royal-burger-novo-lisice"
]

all_dishes = []

for r in restaurants:

    print("Checking restaurant:", r)

    url = f"{BASE}/api/restaurant/{r}"

    try:

        response = requests.get(url, headers=headers)

        print("Status:", response.status_code)

        print(response.text[:300])  # show first part of response

    except Exception as e:

        print("Error:", e)

print("Finished")