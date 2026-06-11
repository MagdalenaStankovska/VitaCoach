🎯 **ADD RECOMMENDATIONS TO GOOGLE CALENDAR** - Quick Start Guide

═══════════════════════════════════════════════════════════════════════════════

## ✨ What's New?

You now have a complete **"Add Recommendations to Google Calendar"** feature! When you accept an AI 
recommendation on the Schedule page, you can add it directly to your Google Calendar with one click.

## 🚀 How to Use (5 Simple Steps)

**1️⃣  Ensure Google Calendar is Connected**
   - Go to navbar
   - Look for "Connect Google Calendar" option
   - Click and authorize with your Google account

**2️⃣  Go to Schedule Page**
   - Click "📅 Schedule" in the navbar
   - Click "🔄 Refresh Calendar" to load recommendations

**3️⃣  Open A Day**
   - Click any day in the calendar grid
   - A modal will show your events and AI suggestions

**4️⃣  Accept a Suggestion**
   - Click the **"Accept"** button next to a suggestion
   - Button will show as active (highlighted in green)

**5️⃣  Add to Calendar**
   - Click **"📅 Add to Calendar"** button (appears after accepting)
   - ✅ Success message appears
   - 📅 Event is automatically added to your Google Calendar

## 📊 What Gets Added to Your Calendar?

### Example Suggestion → Calendar Event:

```
Suggestion Text:
"Workout at gym: 7:00 AM for 45 minutes"

↓

Becomes Calendar Event:
📅 Title:       Workout at gym
🕐 Start Time:  Tomorrow 7:00 AM
⏱️  End Time:   Tomorrow 7:45 AM  
📝 Description: Workout at gym: 7:00 AM for 45 minutes
```

### Smart Features:
✅ Automatically extracts time from suggestion
✅ Detects AM/PM format
✅ Converts 12-hour to 24-hour time
✅ Handles missing times (defaults to 9:00 AM)
✅ Sets 1-hour duration by default (adjustable with endTime)

## 🎨 Visual Guide

```
┌─────────────────────────────────────────────┐
│        SELECT A DAY IN CALENDAR              │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          MODAL OPENS:                        │
│  • Google Calendar events for that day      │
│  • AI suggestions for that day              │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          ACCEPT SUGGESTION:                  │
│  [Accept] [Reject]                          │
│     ↑ Click this                            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│       ACCEPT BUTTON + NEW BUTTON:            │
│  [✓ Accepted] [Rejected] [📅 Add to Cal]   │
│                           ↑ Click this      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          EVENT CREATED:                      │
│  ✅ Event added to calendar: "Workout..."  │
│  (Message disappears after 3 seconds)       │
└─────────────────────────────────────────────┘
```

## 🔴 Troubleshooting

### ❌ "Google Calendar is not connected"
→ Click "Connect Google Calendar" in navbar and authorize

### ❌ "No suggestions detected"  
→ Click "Refresh Calendar" button to analyze your schedule

### ❌ Event not appearing in calendar
→ Wait 5 seconds and refresh your Google Calendar
→ Ensure you're viewing the correct calendar

### ❌ Time is wrong
→ Check your system timezone settings
→ Google Calendar converts UTC to your timezone automatically

## 🛠️ Technical Details

### Backend Changes:
✅ New endpoint: `POST /users/me/calendar/events`
✅ Accepts: title, description, startTime, endTime, location
✅ Returns: success, eventId, eventUrl, title
✅ Auto-refresh Google token if expired

### Frontend Changes:
✅ New API helper: `createCalendarEvent(token, eventData)`
✅ New parser: `parseEventFromSuggestion(suggestion, date)`
✅ New handler: `handleAddEventToCalendar()`
✅ New styling for "Add to Calendar" button

### Files Modified:
📝 `fitness-rag-backend/app.py`
   - Added `CreateCalendarEventRequest` model
   - Added `create_google_calendar_event()` function
   - Added `POST /users/me/calendar/events` endpoint

🎨 `fitness-ai-app/src/ScheduleRecommendations.jsx`
   - Added `parseEventFromSuggestion()` parser
   - Added `handleAddEventToCalendar()` handler
   - Added "Add to Calendar" button UI
   - Added event creation feedback

📚 `fitness-ai-app/src/lib/api.js`
   - Added `createCalendarEvent(token, eventData)` helper

🎨 `fitness-ai-app/src/ScheduleRecommendations.css`
   - Added `.decision-btn.add-to-calendar` styles
   - Added `.event-create-message` styles

## 📋 Requirements

✅ User must be authenticated
✅ Google Calendar must be connected
✅ Valid Google OAuth tokens required
✅ Internet connection (to reach Google Calendar API)

## 🎯 Next Steps / Future Features

Coming soon:
- ⏳ Custom event duration picker
- 🔄 Sync events back into recommendations
- ⚠️  Conflict detection with existing events
- 🏷️  Color coding by activity type
- 🔔 Auto-add reminders/notifications
- 📅 Support for recurring recommendations

## 💡 Tips & Tricks

**💡 Batch Adding**
Accept multiple suggestions, then add them one by one to calendar

**💡 Custom Times**
Edit suggestions manually before accepting if time needs adjustment

**💡 Review in Calendar**
After adding, click the "eventUrl" to open event directly in Google Calendar

**💡 Undo Options**
If event was added incorrectly, delete it from Google Calendar directly

## 📞 Getting Help

Issue: Backend not running?
→ `cd D:\CIIT\fitness-rag-backend`
→ `uvicorn app:app --reload --port 9000`

Issue: Frontend not connecting?
→ Check `API_BASE` in `fitness-ai-app/src/lib/api.js`
→ Ensure it points to `http://127.0.0.1:9000`

Issue: Google Calendar API errors?
→ Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`
→ Check that Google Calendar API is enabled in Google Cloud Console

═══════════════════════════════════════════════════════════════════════════════

**Status:** ✅ Ready to Use
**Version:** 1.0
**Last Updated:** May 2026

Enjoy! 🎉

