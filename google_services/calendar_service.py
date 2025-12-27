from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import uuid


def get_calendar_service(credentials: Credentials):
    """Create Google Calendar service instance"""
    return build("calendar", "v3", credentials=credentials)


def list_events(credentials: Credentials):
    """List upcoming calendar events"""
    service = get_calendar_service(credentials)
    
    # Get events starting from now
    now = datetime.utcnow().isoformat() + "Z"

    events = service.events().list(
        calendarId="primary",
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events.get("items", [])


def create_meet_event(credentials: Credentials, summary: str = "FastAPI Google Meet", duration_minutes: int = 60):
    """Create a calendar event with Google Meet link"""
    service = get_calendar_service(credentials)

    # Create event starting 1 hour from now
    start_time = datetime.utcnow() + timedelta(hours=1)
    end_time = start_time + timedelta(minutes=duration_minutes)

    event = {
        "summary": summary,
        "start": {"dateTime": start_time.isoformat() + "Z", "timeZone": "UTC"},
        "end": {"dateTime": end_time.isoformat() + "Z", "timeZone": "UTC"},
        "conferenceData": {
            "createRequest": {"requestId": str(uuid.uuid4())}
        },
    }

    event = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
    ).execute()

    return event.get("hangoutLink", "No Meet link generated")
