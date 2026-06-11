# Sportmaster Gym Scraper Guide

## Overview
This scraper collects gym information from https://sportmaster.mk/locations including:
- **Gym Name** - Official name of the fitness facility
- **Categories** - Activity types (Fitness, Yoga, Crossfit, etc.)
- **Coordinates** - Latitude & Longitude from Google Maps
- **Address** - Full address information
- **URL** - Direct link to the gym page

## How to Run

### Basic Usage
```bash
cd D:\CIIT\fitness-rag-backend
python sportmaster_scraper.py
```

### What Happens
1. Opens Chromium browser (you'll see it working)
2. Loads https://sportmaster.mk/locations
3. Scrolls to load all gym listings
4. Clicks each gym to extract detailed information
5. Saves all data to `gyms_dataset.json`

### Time Required
- **~3-5 minutes** depending on internet speed
- The script includes cooling periods to avoid being blocked

## Output Format

### File: `gyms_dataset.json`

Each gym entry contains:
```json
{
  "name": "ЦБС Адора",
  "url": "https://sportmaster.mk/location/1290",
  "address": "Skopje, North Macedonia",
  "category": "Кик Бокс, Burn It Up, Функционален тренинг",
  "categories": [
    "Кик Бокс",
    "Burn It Up",
    "Функционален тренинг"
  ],
  "latitude": 41.9979288,
  "longitude": 21.4610119
}
```

## Features

### ✅ Data Collection
- Extracts gym name, address, categories, and coordinates
- Handles multiple category labels per gym
- Stores both combined string and array of categories

### ✅ Reliability
- Retry logic for failed page loads (3 attempts)
- Graceful error handling
- Persistent browser profile to avoid detection
- Cooling periods between gym requests

### ✅ Localization
- Full UTF-8 support for Macedonian text
- Proper character encoding on Windows

## Troubleshooting

### Issue: Browser window doesn't appear
- This is normal if headless=False isn't working on your system
- The script still works in the background

### Issue: Scraper stops
- Press Ctrl+C to stop manually
- Check `gyms_dataset.json` for partial results

### Issue: URL errors (ERR_NAME_NOT_RESOLVED)
- This has been fixed in the latest version
- Make sure you're using the updated `sportmaster_scraper.py`

## Integration with Backend

### Adding to your API
The gym data can be used in your backend similar to restaurants:

```python
# Load gyms data
gyms_dataset = json.load(open("gyms_dataset.json"))

# Find nearest gyms to user location
def find_nearest_gyms(user_lat, user_lng, limit=3):
    # Use haversine distance calculation
    # Sort by distance and return top N
    pass

# Use in recommendations
@app.get("/users/me/nearest-gyms")
def get_nearest_gyms(user_location):
    gyms = find_nearest_gyms(user_location.lat, user_location.lng)
    return gyms
```

## Tips

1. **First Run**: The scraper may take longer the first time as it discovers all gym links
2. **Data Updates**: Run the scraper periodically to update gym information
3. **Stop & Resume**: Results are saved progressively to the JSON file
4. **Performance**: If the scraper is slow, check your internet connection

## Next Steps

Once you have the `gyms_dataset.json`:
1. Add endpoint to get nearest gyms based on user coordinates
2. Integrate with calendar recommendations to suggest nearby gyms
3. Add gym information to workout plans
4. Show gym details and categories in the mobile app

---

**Created**: April 2026
**Last Updated**: With URL fix for proper domain/path separation

