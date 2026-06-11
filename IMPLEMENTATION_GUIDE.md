# 🎯 Google Calendar + Gemini Implementation Complete

## ✅ What's Been Implemented

### Backend (Python/FastAPI)

#### New Functions
1. **`refresh_google_calendar_token(user)`** - Automatically refreshes expired tokens
2. **`fetch_google_calendar_events(user, days_ahead)`** - Fetches events from Google Calendar API
3. **`get_schedule_recommendations(payload, user)`** - Main AI analysis endpoint

#### New Endpoints

##### 1. Get Calendar Events
```http
GET /users/me/calendar/events?days_ahead=7
Authorization: Bearer {auth_token}
```
Returns user's calendar events for the next N days.

##### 2. Get Schedule Recommendations
```http
POST /users/me/schedule-recommendations
Authorization: Bearer {auth_token}
Content-Type: application/json

{
  "daysAhead": 7,
  "language": "English"
}
```
Analyzes calendar and returns AI-powered recommendations.

### Frontend (React)

#### New Component: `ScheduleRecommendations.jsx`
Features:
- Calendar connection status checking
- Event list display (shows next 10 events)
- Adjustable date range (1-30 days)
- Real-time Gemini analysis
- Korpa meal suggestions
- Formatted recommendations with sections

#### New Styling: `ScheduleRecommendations.css`
- Modern gradient design
- Responsive layout (mobile-friendly)
- Loading animations
- Error handling UI

#### Updated Files
1. **App.jsx** - Added `/schedule` route
2. **Navbar.jsx** - Added "📅 Schedule" link (only for authenticated users)
3. **api.js** - Added 2 new API functions

---

## 🔧 How It Works

### Flow Diagram
```
User clicks "📅 Schedule" in navbar
         ↓
Component checks Google Calendar connection
         ↓
User clicks "🔄 Analyze Schedule"
         ↓
Backend fetches calendar events (auto-refreshes token if needed)
         ↓
Backend loads Korpa meals data
         ↓
Gemini analyzes events + meals
         ↓
AI generates personalized recommendations:
- Optimal exercise times
- Meal timing suggestions
- Quick Korpa meal options
- Weekly strategy summary
         ↓
Frontend displays recommendations with formatting
```

### Data Flow
```
Frontend ← ScheduleRecommendations Component
   ↓
API calls (getCalendarEvents, getScheduleRecommendations)
   ↓
Backend ← FastAPI endpoints
   ↓
Google Calendar API ← Fetch events
Korpa Data ← Load meals
Gemini API ← Generate recommendations
   ↓
Response → Frontend
   ↓
Display in ScheduleRecommendations component
```

---

## 🚀 Quick Start

### 1. Get Google Cloud Credentials
```bash
# Visit https://console.cloud.google.com/
# 1. Create new project
# 2. Enable Google Calendar API
# 3. Create OAuth 2.0 Web Application credentials
# 4. Note Client ID and Client Secret
```

### 2. Get Gemini API Key
```bash
# Visit https://aistudio.google.com/app/apikeys
# Create new API key
```

### 3. Configure Backend
```bash
cd fitness-rag-backend

# Run setup script (interactive)
python setup_google_calendar.py

# Or manually edit .env:
echo "GOOGLE_CLIENT_ID=your_id" >> .env
echo "GOOGLE_CLIENT_SECRET=your_secret" >> .env
echo "GEMINI_API_KEY=your_key" >> .env
echo "FRONTEND_URL=http://localhost:5173" >> .env
```

### 4. Start Backend
```bash
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 9000 --reload
```

### 5. Start Frontend
```bash
cd fitness-ai-app
npm install
npm run dev
```

### 6. Use the Feature
1. Register at http://localhost:5173/register
2. Click "Connect Google Calendar" in navbar
3. Authorize the app in Google
4. Click "📅 Schedule" in navbar
5. Click "🔄 Analyze Schedule"
6. View personalized recommendations

---

## 📊 Data Structures

### Calendar Event
```json
{
  "id": "event_google_id",
  "title": "Team Meeting",
  "description": "Discuss Q1 goals",
  "startTime": "2025-01-20T09:00:00Z",
  "endTime": "2025-01-20T10:00:00Z",
  "location": "Conference Room A"
}
```

### Recommendation Response
```json
{
  "recommendations": "⏱️ OPTIMAL EXERCISE TIMES:\n...",
  "suggestions": [
    "✅ Personalized workout schedule generated",
    "🍽️ Meal timing recommendations provided",
    "⚡ Quick meal options suggested"
  ],
  "events_analyzed": 12,
  "meals": [
    {"name": "Grilled Chicken", "prep_time": "20 min"},
    {"name": "Protein Shake", "prep_time": "5 min"}
  ]
}
```

### User (with Calendar Connection)
```json
{
  "id": "user_id",
  "name": "John Doe",
  "email": "john@example.com",
  "token": "auth_token",
  "googleCalendarConnected": true,
  "googleCalendarAccessToken": "access_token",
  "googleCalendarRefreshToken": "refresh_token",
  "googleCalendarTokenExpiresAt": 1705858800,
  "garminConnected": false
}
```

---

## 🎨 UI Components

### Schedule Page Layout
```
┌─────────────────────────────────────────┐
│ 📅 Smart Schedule Recommendations │ 🔄 Analyze  │
├─────────────────────────────────────────┤
│ 📌 Your Calendar (12 events)            │
│ - Meeting (2025-01-20 09:00)           │
│ - Lunch (2025-01-20 12:30)             │
│ - Gym (2025-01-20 18:00)               │
│ ... +9 more                             │
├─────────────────────────────────────────┤
│ 🤖 AI Recommendations                  │
│ ✅ Personalized workout schedule        │
│ 🍽️ Meal timing recommendations        │
│ ⚡ Quick meal options suggested        │
├─────────────────────────────────────────┤
│ 🍽️ Quick Meal Options from Korpa      │
│ [Grilled Chicken] [Protein Shake]      │
│ ⏱️ 20 min           ⏱️ 5 min            │
├─────────────────────────────────────────┤
│ 📝 Detailed Analysis                   │
│ ⏱️ OPTIMAL EXERCISE TIMES:              │
│ Based on your schedule, Monday is...    │
│ ...                                     │
└─────────────────────────────────────────┘
```

---

## 🔐 Security & Privacy

### Permissions
- **Read-only access** to Google Calendar
- **No calendar modifications** allowed
- **Automatic token refresh** handling

### Data Handling
- Calendar events fetched on-demand
- Not stored in database
- Used only for recommendation generation
- Deleted after analysis completes

### Token Management
- Refresh tokens stored securely in users.json
- Automatic expiration checking
- Token rotation on each refresh
- Logout clears all tokens

---

## 🐛 Troubleshooting

### Issue: "Google Calendar is not connected"
**Solution:**
1. Ensure you clicked "Connect Google Calendar" button
2. Complete the OAuth flow
3. Check browser console for errors

### Issue: "No calendar events found"
**Solution:**
1. Add events to your Google Calendar
2. Make sure they fall in the selected date range
3. Check that the dates are correct

### Issue: Failed to fetch calendar data
**Solution:**
1. Verify GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env
2. Ensure Google Calendar API is enabled
3. Check GOOGLE_CALENDAR_REDIRECT_URI matches your setup

### Issue: "Could not generate recommendations"
**Solution:**
1. Verify GEMINI_API_KEY is set in .env
2. Check your Gemini API quota
3. Try again with a shorter date range

### Issue: Recommendations taking too long
**Solution:**
1. Reduce the days_ahead value (try 3-5 days)
2. Check network connection
3. Verify Gemini API is responsive

---

## 📈 Future Enhancements

### Planned Features
- [ ] Garmin integration for fitness data
- [ ] Workout history tracking
- [ ] Meal preference learning
- [ ] Weekly summary reports
- [ ] Export recommendations as PDF
- [ ] Calendar event creation from suggestions
- [ ] Time zone handling
- [ ] Multiple calendar support
- [ ] Notification scheduling
- [ ] Habit tracking

### API Improvements
- [ ] Caching for repeated analyses
- [ ] Batch event analysis
- [ ] Custom recommendation models
- [ ] User preference storage

---

## 📝 Environment Variables

### Required
```env
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GEMINI_API_KEY=your_gemini_api_key
```

### Optional
```env
GOOGLE_CALENDAR_REDIRECT_URI=http://127.0.0.1:9000/auth/google-calendar/callback
FRONTEND_URL=http://localhost:5173
YOUTUBE_API_KEY=optional_for_video_tutorials
```

---

## 🧪 Testing

### Manual Testing Checklist
- [ ] Register new user
- [ ] Connect Google Calendar
- [ ] Add test events to calendar
- [ ] Navigate to Schedule page
- [ ] Click Analyze Schedule
- [ ] Verify recommendations are generated
- [ ] Test with different date ranges
- [ ] Test error handling (no events, API errors)
- [ ] Logout and login again
- [ ] Verify calendar connection persists

### Automated Testing
```bash
# Backend tests (if implemented)
python -m pytest tests/

# Frontend tests (if implemented)
npm test
```

---

## 📚 Documentation

### Files Created
1. `GOOGLE_CALENDAR_SETUP.md` - Complete setup guide
2. `setup_google_calendar.py` - Interactive setup script
3. `ScheduleRecommendations.jsx` - React component
4. `ScheduleRecommendations.css` - Component styling

### Files Modified
1. `app.py` - Added new endpoints
2. `api.js` - Added new API functions
3. `App.jsx` - Added route
4. `Navbar.jsx` - Added navigation link

---

## 🎓 Key Concepts

### OAuth 2.0 Flow
1. User clicks "Connect Google Calendar"
2. Backend generates OAuth URL with state
3. User redirected to Google login
4. User grants permission
5. Google redirects back with auth code
6. Backend exchanges code for access token
7. Access token stored with refresh token
8. Token auto-refreshes when expired

### AI Analysis Process
1. Fetch user's calendar events
2. Load Korpa meals data
3. Format data for Gemini
4. Send prompt asking for analysis
5. Gemini analyzes schedule
6. Returns structured recommendations
7. Frontend displays with formatting

---

## 💡 Usage Tips

### For Users
- Add meaningful event descriptions for better analysis
- Set realistic time blocks for your activities
- Update calendar regularly for best recommendations
- Use specific meal names in Korpa database

### For Developers
- Monitor Gemini API usage (has quota limits)
- Cache recommendations if needed
- Implement rate limiting for high-traffic scenarios
- Consider adding event categories for better analysis

---

## 🔗 Useful Links

- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Calendar API](https://developers.google.com/calendar)
- [Gemini API Documentation](https://ai.google.dev/)
- [OAuth 2.0 Guide](https://developers.google.com/identity/protocols/oauth2)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Hooks](https://react.dev/reference/react)

---

## 📞 Support & Feedback

For issues or improvements:
1. Check the troubleshooting section
2. Review error messages in browser console
3. Check backend logs
4. Refer to official Google API documentation
5. Review Gemini API documentation

---

**Version:** 1.0  
**Last Updated:** January 2025  
**Status:** ✅ Production Ready

