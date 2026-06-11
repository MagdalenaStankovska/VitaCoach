"""
Testing Examples for Google Calendar + Gemini Integration

This file contains example code snippets for testing the implementation.
"""

# ============================================================================
# 1. TESTING THE BACKEND DIRECTLY (Using curl or Python requests)
# ============================================================================

"""
# Test 1: Connect Google Calendar (Get OAuth URL)
curl -X POST http://127.0.0.1:9000/users/me/connections/google-calendar \
  -H "Authorization: Bearer {user_token}" \
  -H "Content-Type: application/json"

# Should return something like:
{
  "authUrl": "https://accounts.google.com/o/oauth2/v2/auth?..."
}

# Then visit the authUrl in browser to authorize
"""

# ============================================================================
# 2. PYTHON TEST SCRIPT
# ============================================================================

import requests
import json

BASE_URL = "http://127.0.0.1:9000"

def test_calendar_integration():
    """Test the calendar integration"""
    
    # Step 1: Register user
    print("\n[Step 1] Register User")
    print("-" * 60)
    
    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "testpass123"
        }
    )
    
    if register_response.status_code == 200:
        user_data = register_response.json()
        token = user_data.get("token")
        print(f"✅ User registered: {user_data['user']['name']}")
        print(f"Token: {token[:20]}...")
    else:
        print(f"❌ Registration failed: {register_response.text}")
        return
    
    # Step 2: Get OAuth URL for Google Calendar
    print("\n[Step 2] Get Google Calendar OAuth URL")
    print("-" * 60)
    
    connect_response = requests.post(
        f"{BASE_URL}/users/me/connections/google-calendar",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if connect_response.status_code == 200:
        auth_url = connect_response.json().get("authUrl")
        print(f"✅ OAuth URL generated")
        print(f"Visit: {auth_url[:100]}...")
        print("\nNote: You need to manually visit this URL and authorize in browser")
        print("Then check calendar events using the token")
    else:
        print(f"❌ Failed to get OAuth URL: {connect_response.text}")
    
    # Step 3: Get calendar events (after authorization)
    print("\n[Step 3] Fetch Calendar Events")
    print("-" * 60)
    print("Note: Run this after completing OAuth flow")
    
    calendar_response = requests.get(
        f"{BASE_URL}/users/me/calendar/events?days_ahead=7",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if calendar_response.status_code == 200:
        events_data = calendar_response.json()
        events = events_data.get("events", [])
        print(f"✅ Found {len(events)} calendar events")
        for event in events[:3]:  # Show first 3
            print(f"  - {event['title']} ({event['startTime']})")
    else:
        print(f"⚠️ Calendar not connected or error: {calendar_response.text}")
    
    # Step 4: Get recommendations
    print("\n[Step 4] Get Schedule Recommendations")
    print("-" * 60)
    
    if calendar_response.status_code == 200:
        recommendations_response = requests.post(
            f"{BASE_URL}/users/me/schedule-recommendations",
            headers={"Authorization": f"Bearer {token}"},
            json={"daysAhead": 7, "language": "English"}
        )
        
        if recommendations_response.status_code == 200:
            recommendations = recommendations_response.json()
            print(f"✅ Recommendations generated")
            print(f"Events analyzed: {recommendations.get('events_analyzed')}")
            print(f"Suggestions: {len(recommendations.get('suggestions', []))}")
            print(f"Meals: {len(recommendations.get('meals', []))}")
            print(f"\nRecommendations preview:")
            print(recommendations['recommendations'][:500] + "...")
        else:
            print(f"❌ Failed to get recommendations: {recommendations_response.text}")


# ============================================================================
# 3. REACT COMPONENT TEST
# ============================================================================

"""
// In your React test file (e.g., ScheduleRecommendations.test.jsx)

import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider } from './auth/AuthContext';
import ScheduleRecommendations from './ScheduleRecommendations';

describe('ScheduleRecommendations', () => {
  it('should display schedule page when authenticated with calendar', async () => {
    const mockUser = {
      id: 'test-user',
      name: 'Test User',
      email: 'test@example.com',
      googleCalendarConnected: true,
    };

    render(
      <AuthProvider>
        <ScheduleRecommendations />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/📅 Smart Schedule Recommendations/i)).toBeInTheDocument();
    });
  });

  it('should show connection message when calendar not connected', () => {
    const mockUser = {
      id: 'test-user',
      name: 'Test User',
      email: 'test@example.com',
      googleCalendarConnected: false,
    };

    render(
      <AuthProvider>
        <ScheduleRecommendations />
      </AuthProvider>
    );

    expect(screen.getByText(/Google Calendar Not Connected/i)).toBeInTheDocument();
  });

  it('should load and display calendar events', async () => {
    // Test that calendar events are fetched and displayed
  });

  it('should generate recommendations on button click', async () => {
    // Test that recommendations are generated
  });
});
"""

# ============================================================================
# 4. MOCK DATA FOR TESTING
# ============================================================================

MOCK_CALENDAR_EVENTS = [
    {
        "id": "event1",
        "title": "Team Meeting",
        "description": "Weekly sync",
        "startTime": "2025-01-20T09:00:00Z",
        "endTime": "2025-01-20T10:00:00Z",
        "location": "Conference Room A"
    },
    {
        "id": "event2",
        "title": "Lunch Break",
        "description": "",
        "startTime": "2025-01-20T12:00:00Z",
        "endTime": "2025-01-20T13:00:00Z",
        "location": ""
    },
    {
        "id": "event3",
        "title": "Gym",
        "description": "Evening workout",
        "startTime": "2025-01-20T18:00:00Z",
        "endTime": "2025-01-20T19:30:00Z",
        "location": "Fitness Center"
    },
]

MOCK_RECOMMENDATIONS = {
    "recommendations": """
⏱️ OPTIMAL EXERCISE TIMES:
Based on your schedule, you have excellent opportunities for exercise:
- Monday: 6:00-7:30 PM - Evening workout (1.5 hours available)
- Tuesday: 7:00-8:00 AM - Morning session (1 hour available)
- Wednesday: 12:30-1:30 PM - Lunch hour fitness (1 hour available)

🍽️ MEAL SUGGESTIONS:
- Breakfast: 7:00 AM (pre-workout for Tuesday)
- Lunch: 12:30 PM (light meal before gym)
- Dinner: 7:30 PM (post-workout recovery)

⚡ QUICK MEAL OPTIONS FROM KORPA:
For busy meetings, consider:
- Protein bowls (15 min prep)
- Salads (10 min prep)
- Smoothies (5 min prep)

📅 WEEKLY OVERVIEW:
You have a solid schedule for maintaining fitness. The best strategy is:
1. Morning workouts on Tuesday (before meeting)
2. Evening workouts on Monday, Wednesday, Friday
3. Quick meals on busy days (Tuesday, Thursday)
    """,
    "suggestions": [
        "✅ Personalized workout schedule generated based on your calendar",
        "🍽️ Meal timing recommendations provided",
        "⚡ Quick meal options suggested for busy periods"
    ],
    "events_analyzed": 15,
    "meals": [
        {"name": "Grilled Chicken Salad", "prep_time": "15 min"},
        {"name": "Protein Bowl", "prep_time": "20 min"},
        {"name": "Protein Smoothie", "prep_time": "5 min"},
        {"name": "Pasta & Veggies", "prep_time": "25 min"},
        {"name": "Fish & Rice", "prep_time": "30 min"},
    ]
}

# ============================================================================
# 5. FRONTEND TESTING UTILITY
# ============================================================================

"""
// In a test utility file

export async function testScheduleAPI(token) {
  try {
    // Test 1: Get calendar events
    console.log('Testing calendar events...');
    const eventsRes = await fetch('http://127.0.0.1:9000/users/me/calendar/events?days_ahead=7', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const events = await eventsRes.json();
    console.log('✅ Calendar events:', events);

    // Test 2: Get recommendations
    console.log('Testing recommendations...');
    const recsRes = await fetch('http://127.0.0.1:9000/users/me/schedule-recommendations', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ daysAhead: 7, language: 'English' })
    });
    const recommendations = await recsRes.json();
    console.log('✅ Recommendations:', recommendations);

    return { events, recommendations };
  } catch (error) {
    console.error('❌ API test failed:', error);
  }
}
"""

# ============================================================================
# 6. INTEGRATION TEST SCENARIO
# ============================================================================

"""
// Test Scenario: Full User Flow

1. User Registration
   - Register with email, password, name
   - Receive auth token

2. Google Calendar Connection
   - Click "Connect Google Calendar" button
   - Get OAuth URL
   - Complete OAuth flow
   - Receive access token and refresh token
   - Store in user profile

3. Calendar Analysis
   - Navigate to Schedule page
   - Click "Analyze Schedule" button
   - Fetch calendar events for 7 days
   - Call Gemini API with events + meals data
   - Display recommendations

4. Verify Results
   - Check if events are loaded correctly
   - Check if AI recommendations are generated
   - Check if meal suggestions are displayed
   - Verify no sensitive data is exposed
"""

# ============================================================================
# 7. CURL COMMANDS FOR MANUAL TESTING
# ============================================================================

"""
# Register user
curl -X POST http://127.0.0.1:9000/auth/register \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "password123"
  }'

# Get current user
curl -X GET http://127.0.0.1:9000/auth/me \\
  -H "Authorization: Bearer YOUR_TOKEN"

# Connect to Google Calendar
curl -X POST http://127.0.0.1:9000/users/me/connections/google-calendar \\
  -H "Authorization: Bearer YOUR_TOKEN"

# Get calendar events
curl -X GET "http://127.0.0.1:9000/users/me/calendar/events?days_ahead=7" \\
  -H "Authorization: Bearer YOUR_TOKEN"

# Get recommendations
curl -X POST http://127.0.0.1:9000/users/me/schedule-recommendations \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "daysAhead": 7,
    "language": "English"
  }'

# Logout
curl -X POST http://127.0.0.1:9000/auth/logout \\
  -H "Authorization: Bearer YOUR_TOKEN"
"""

if __name__ == "__main__":
    print("=" * 70)
    print("Google Calendar + Gemini Integration - Testing Examples")
    print("=" * 70)
    print("\nChoose what to test:")
    print("1. Run full backend test")
    print("2. View mock data")
    print("3. View curl commands")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        test_calendar_integration()
    elif choice == "2":
        print("\nMock Calendar Events:")
        print(json.dumps(MOCK_CALENDAR_EVENTS, indent=2))
        print("\nMock Recommendations:")
        print(json.dumps(MOCK_RECOMMENDATIONS, indent=2))
    elif choice == "3":
        print("\nCurl Commands - Paste in terminal:")
        print("See comments in this file for full curl examples")

