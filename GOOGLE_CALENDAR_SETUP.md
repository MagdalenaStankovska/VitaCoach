# 📅 Google Calendar + Gemini AI Integration Guide

## Overview
This feature connects your Google Calendar with Gemini AI to provide smart recommendations for:
- **Optimal Exercise Times**: Based on your schedule availability
- **Meal Timing**: Personalized nutrition recommendations
- **Quick Meals from Korpa**: When you don't have time to cook

---

## 🚀 Setup Instructions

### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (name it something like "VitaCoach")
3. Enable the Google Calendar API:
   - Search for "Google Calendar API"
   - Click "Enable"

### Step 2: Create OAuth 2.0 Credentials
1. Go to "Credentials" in the left menu
2. Click "Create Credentials" → "OAuth client ID"
3. Choose "Web Application"
4. Add Authorized Redirect URIs:
   - `http://localhost:5173` (for development)
   - `http://localhost:9000/auth/google-calendar/callback` (backend callback)
   - `http://127.0.0.1:9000/auth/google-calendar/callback` (backend callback)
   - Add your production domain when deploying

5. Copy the Client ID and Client Secret

### Step 3: Update .env File
In `fitness-rag-backend/.env`, add:
```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_CALENDAR_REDIRECT_URI=http://127.0.0.1:9000/auth/google-calendar/callback
GEMINI_API_KEY=your_gemini_api_key
```

### Step 4: Frontend Configuration
The frontend should already have the necessary setup. Just ensure:
- User registers/logs in
- Clicks "Connect Google Calendar" button in navbar
- Authorizes the app to access their calendar

---

## 📱 How to Use

### 1. Register or Login
```bash
Navigate to /register or /login
```

### 2. Connect Google Calendar
- Click "Connect Google Calendar" in the navbar
- Follow the OAuth flow
- Grant permission to access your calendar

### 3. View Schedule Recommendations
- Click "📅 Schedule" in the navbar
- Click "🔄 Analyze Schedule" button
- AI will analyze your calendar and provide recommendations

### 4. Adjust Time Range
- Use the "Days to analyze" input to change the range (1-30 days)
- Click "Analyze" to refresh recommendations

---

## 🔌 API Endpoints

### Fetch Calendar Events
```
GET /users/me/calendar/events?days_ahead=7
Authorization: Bearer {token}
```

**Response:**
```json
{
  "events": [
    {
      "id": "event_id",
      "title": "Meeting",
      "description": "Team standup",
      "startTime": "2025-01-15T09:00:00Z",
      "endTime": "2025-01-15T10:00:00Z",
      "location": "Office"
    }
  ],
  "connected": true
}
```

### Get Schedule Recommendations
```
POST /users/me/schedule-recommendations
Authorization: Bearer {token}
Content-Type: application/json

{
  "daysAhead": 7,
  "language": "English"
}
```

**Response:**
```json
{
  "recommendations": "⏱️ OPTIMAL EXERCISE TIMES:\n...",
  "suggestions": [
    "✅ Personalized workout schedule generated based on your calendar",
    "🍽️ Meal timing recommendations provided"
  ],
  "events_analyzed": 12,
  "meals": [
    {"name": "Grilled Chicken Salad", "prep_time": "15 min"},
    {"name": "Protein Smoothie", "prep_time": "5 min"}
  ]
}
```

---

## 🎯 Features

### Smart Analysis
- Analyzes your calendar events to identify free slots
- Suggests workout intensity based on time availability
- Recommends meal timing around your schedule

### Korpa Integration
- Shows quick meal options when you're busy
- Suggests nutritious meals that fit prep time constraints
- Lists restaurants/meals available for quick orders

### AI-Powered
- Uses Gemini 2.0 Flash for intelligent recommendations
- Supports English and Macedonian languages
- Generates personalized weekly strategy

---

## 🔒 Privacy & Permissions

This app requests:
- **Calendar read-only access**: To analyze your schedule
- **Does NOT modify your calendar**: Only reads event data
- **Does NOT store calendar data**: Recommendations are generated on-the-fly

Your calendar data is used only to:
1. Fetch your events
2. Generate recommendations
3. Never shared with third parties
4. Deleted after analysis

---

## 🛠️ Troubleshooting

### "Google Calendar is not connected"
- Make sure you clicked "Connect Google Calendar" and authorized the app
- Check that your token has not expired
- Try disconnecting and reconnecting

### "No calendar events found"
- Add events to your Google Calendar first
- Make sure they fall within the selected date range
- Refresh your browser cache

### "Calendar fetch error"
- Verify your Google credentials are valid
- Check that GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set
- Ensure GOOGLE_CALENDAR_REDIRECT_URI matches your environment

### Token Expired
- Refresh tokens are handled automatically
- If you see an error, log out and log back in

---

## 📦 Dependencies

### Backend
- `google.genai` - Gemini API client
- `requests` - For Google OAuth token exchange
- `fastapi` - API framework
- `pydantic` - Data validation

### Frontend
- React with hooks
- Fetch API for HTTP requests

---

## 🎓 Example Use Cases

### Case 1: Busy Professional
```
Calendar: 9AM-5PM meetings, 6PM gym available
AI Recommendation: Workout at 6PM (1 hour), light meals pre-work
Korpa Suggestions: Protein shakes for quick meals between meetings
```

### Case 2: Student
```
Calendar: Classes 10AM-3PM, evening free
AI Recommendation: Can fit 2-hour workout in evening
Korpa Suggestions: High-protein quick meals for lunch between classes
```

### Case 3: Flexible Schedule
```
Calendar: Scattered events throughout day
AI Recommendation: Multiple small workouts (HIIT) possible
Korpa Suggestions: Flexible meal timing with various options
```

---

## 📝 Notes

- The feature automatically refreshes Google tokens when expired
- Calendar analysis is done in real-time (no caching)
- Recommendations are personalized per user
- Works with any Google Calendar (including shared calendars if permitted)

---

## 🚀 Deployment

When deploying to production:

1. Update FRONTEND_URL in backend .env:
```env
FRONTEND_URL=https://yourdomain.com
GOOGLE_CALENDAR_REDIRECT_URI=https://yourdomain.com/auth/google-calendar/callback
```

2. Add production domain to Google OAuth credentials:
   - Add `https://yourdomain.com` to authorized origins
   - Add `https://yourdomain.com/auth/google-calendar/callback` to redirect URIs

3. Set secure environment variables on your hosting platform

---

## 📞 Support

If you encounter issues:
1. Check the browser console for error messages
2. Check backend logs for API errors
3. Verify Google Cloud credentials
4. Ensure CORS is properly configured

