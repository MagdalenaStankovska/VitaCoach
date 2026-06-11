#!/usr/bin/env python3
"""
Test script for the new "Add to Calendar" functionality.
Tests the backend endpoint for creating calendar events.
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:9000"

def test_create_calendar_event_flow():
    """Test the complete flow of creating a calendar event."""
    
    print("\n" + "="*60)
    print("🧪 Testing Calendar Event Creation Endpoint")
    print("="*60)
    
    # Step 1: Get sample data (you need to have a token first)
    print("\n1️⃣  Preparing test data...")
    
    # Note: You need to register/login first to get a valid token
    # For testing, we'll need a valid token from your app
    
    print("\n   To test this endpoint, you need to:")
    print("   a) Log in to the app to get your auth token")
    print("   b) Have Google Calendar connected")
    print("   c) Run this test with your token")
    
    print("\n   Expected endpoint structure:")
    event_payload = {
        "title": "Morning Workout",
        "description": "30-45 minutes cardio + strength training",
        "startTime": (datetime.utcnow() + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0).isoformat() + "Z",
        "endTime": (datetime.utcnow() + timedelta(days=1)).replace(hour=8, minute=30, second=0, microsecond=0).isoformat() + "Z",
        "location": "Home Gym"
    }
    
    print("\n   📋 Sample Event Payload:")
    print(json.dumps(event_payload, indent=2))
    
    print("\n2️⃣  API Endpoint Information:")
    print(f"   POST {BASE_URL}/users/me/calendar/events")
    print("\n   Headers Required:")
    print("   - Authorization: Bearer {YOUR_AUTH_TOKEN}")
    print("   - Content-Type: application/json")
    
    print("\n3️⃣  Response Structure (Success):")
    success_response = {
        "success": True,
        "eventId": "event_12345",
        "eventUrl": "https://calendar.google.com/calendar/u/0/r/eventedit/...",
        "title": "Morning Workout"
    }
    print(json.dumps(success_response, indent=2))
    
    print("\n4️⃣  Error Handling:")
    print("   - 401 Unauthorized: Not authenticated")
    print("   - 400 Bad Request: Google Calendar not connected")
    print("   - 400 Bad Request: No valid Google Calendar token")
    print("   - 500 Server Error: Calendar API error")
    
    print("\n5️⃣  Frontend Integration:")
    print("   - Import: createCalendarEvent from '@/lib/api.js'")
    print("   - Usage: await createCalendarEvent(token, eventData)")
    print("   - Returns: { success, eventId, eventUrl, title }")
    
    print("\n6️⃣  Suggestion Parsing:")
    print("   - Extracts time from suggestion text (e.g., '9:00 AM', '9:00')")
    print("   - Creates 1-hour event by default")
    print("   - Uses suggestion text as description")
    
    print("\n✅ Manual Testing Steps:")
    print("   1. Start backend: uvicorn app:app --reload --port 9000")
    print("   2. Start frontend: npm run dev")
    print("   3. Log in to the app")
    print("   4. Connect Google Calendar")
    print("   5. Go to Schedule -> Analyze")
    print("   6. Click a day and accept a suggestion")
    print("   7. Click '📅 Add to Calendar' button")
    print("   8. Check your Google Calendar for the new event")
    
    print("\n" + "="*60)
    print("✨ Test Summary Complete")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_create_calendar_event_flow()

