#!/usr/bin/env python3
"""
Quick setup helper for Google Calendar integration
Run this after setting up your Google Cloud credentials
"""

import json
import os
from pathlib import Path

def setup_google_calendar():
    print("\n" + "="*60)
    print("🚀 Google Calendar + Gemini Integration Setup")
    print("="*60 + "\n")
    
    print("This setup will help you configure Google Calendar integration.")
    print("\nBefore running this, you need:")
    print("1. A Google Cloud Project")
    print("2. Google Calendar API enabled")
    print("3. OAuth 2.0 credentials (Web Application)")
    print("4. Your Gemini API key\n")
    
    # Check if .env exists
    env_path = Path("fitness-rag-backend/.env")
    
    print("Step 1: Enter your credentials")
    print("-" * 60)
    
    google_client_id = input("Enter your GOOGLE_CLIENT_ID: ").strip()
    google_client_secret = input("Enter your GOOGLE_CLIENT_SECRET: ").strip()
    gemini_api_key = input("Enter your GEMINI_API_KEY: ").strip()
    
    # Get environment
    env_type = input("\nAre you setting up for (development/production)? [development]: ").strip().lower()
    if env_type not in ["development", "production"]:
        env_type = "development"
    
    if env_type == "development":
        redirect_uri = "http://127.0.0.1:9000/auth/google-calendar/callback"
        frontend_url = "http://localhost:5173"
    else:
        frontend_url = input("Enter your production domain (e.g., https://example.com): ").strip()
        redirect_uri = f"{frontend_url}/auth/google-calendar/callback"
    
    # Create .env content
    env_content = f"""# Google Cloud Configuration
GOOGLE_CLIENT_ID={google_client_id}
GOOGLE_CLIENT_SECRET={google_client_secret}
GOOGLE_CALENDAR_REDIRECT_URI={redirect_uri}

# Gemini API
GEMINI_API_KEY={gemini_api_key}

# Frontend URL for redirects
FRONTEND_URL={frontend_url}

# Database (if using PostgreSQL)
# DB_NAME=fitness_rag
# DB_USER=postgres
# DB_PASSWORD=your_password
# DB_HOST=localhost
# DB_PORT=5432

# YouTube API (optional)
# YOUTUBE_API_KEY=your_youtube_api_key
"""
    
    # Write to .env file
    print(f"\nStep 2: Saving configuration to {env_path}")
    print("-" * 60)
    
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(env_content)
    print(f"✅ Configuration saved to {env_path}")
    
    # Verify setup
    print("\nStep 3: Verification")
    print("-" * 60)
    
    checks = [
        (Path("fitness-rag-backend/app.py").exists(), "Backend app.py exists"),
        (Path("fitness-ai-app/src/ScheduleRecommendations.jsx").exists(), "Frontend ScheduleRecommendations component exists"),
        (env_path.exists(), "Environment file created"),
        (google_client_id, "Google Client ID provided"),
        (google_client_secret, "Google Client Secret provided"),
        (gemini_api_key, "Gemini API Key provided"),
    ]
    
    all_good = True
    for check, description in checks:
        status = "✅" if check else "❌"
        print(f"{status} {description}")
        if not check:
            all_good = False
    
    print("\n" + "="*60)
    if all_good:
        print("🎉 Setup complete! Next steps:")
        print("-" * 60)
        print("1. Start the backend:")
        print("   cd fitness-rag-backend")
        print("   python -m uvicorn app:app --host 127.0.0.1 --port 9000 --reload")
        print("\n2. Start the frontend:")
        print("   cd fitness-ai-app")
        print("   npm run dev")
        print("\n3. Visit http://localhost:5173")
        print("4. Register and connect your Google Calendar")
        print("5. Go to the Schedule page to see recommendations")
        print("\n📚 For more details, see GOOGLE_CALENDAR_SETUP.md")
    else:
        print("⚠️  Some checks failed. Please review the configuration.")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    setup_google_calendar()

