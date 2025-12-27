from fastapi import APIRouter, HTTPException
from auth.router import get_credentials
from google_services.calendar_service import list_events, create_meet_event

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/events")
def get_events():
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return list_events(credentials)


@router.post("/meet")
def create_meet():
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return {"meet_link": create_meet_event(credentials)}
