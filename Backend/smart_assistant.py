"""
Smart Assistant Service
Single endpoint that aggregates Google Calendar, Tasks & Gmail data 
and uses Gemini AI to provide intelligent task management advice
"""
from google import genai
from google.genai import types
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import GEMINI_API_KEY
import base64

# Configure Gemini client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def get_all_events(credentials: Credentials, days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Fetch all calendar events for the next N days"""
    service = build("calendar", "v3", credentials=credentials)
    
    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"
    
    events = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=50,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    
    return events.get("items", [])


def get_all_tasks(credentials: Credentials) -> List[Dict[str, Any]]:
    """Fetch all pending tasks from all task lists"""
    service = build("tasks", "v1", credentials=credentials)
    
    all_tasks = []
    
    # Get all task lists
    task_lists = service.tasklists().list(maxResults=10).execute()
    
    for task_list in task_lists.get("items", []):
        list_id = task_list.get("id")
        list_name = task_list.get("title", "Unknown List")
        
        # Get tasks from this list
        tasks = service.tasks().list(
            tasklist=list_id,
            showCompleted=False,
            maxResults=100
        ).execute()
        
        for task in tasks.get("items", []):
            task["listName"] = list_name
            all_tasks.append(task)
    
    return all_tasks


def get_unread_emails(credentials: Credentials, max_results: int = 10) -> List[Dict[str, Any]]:
    """Fetch unread emails that contain tasks, action items, or pending work from clients"""
    service = build("gmail", "v1", credentials=credentials)
    
    # Query for unread emails with task-related keywords
    # Filters for emails likely containing pending tasks or client requests
    task_keywords = [
        "action required",
        "pending",
        "deadline",
        "urgent",
        "please review",
        "waiting for",
        "follow up",
        "task",
        "request",
        "asap",
        "due date",
        "by tomorrow",
        "needs your",
        "reminder",
        "priority",
        "important"
    ]
    
    # Build Gmail search query: is:unread AND (keyword1 OR keyword2 OR ...)
    keywords_query = " OR ".join([f'"{kw}"' for kw in task_keywords])
    search_query = f"is:unread ({keywords_query})"
    
    results = service.users().messages().list(
        userId="me",
        maxResults=max_results,
        q=search_query
    ).execute()
    
    messages = results.get("messages", [])
    
    detailed_emails = []
    for msg in messages:
        try:
            msg_detail = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full"
            ).execute()
            
            headers = {h["name"]: h["value"] for h in msg_detail.get("payload", {}).get("headers", [])}
            
            # Extract body content
            body = ""
            payload = msg_detail.get("payload", {})
            
            if "parts" in payload:
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/plain":
                        data = part.get("body", {}).get("data", "")
                        if data:
                            body = base64.urlsafe_b64decode(data).decode("utf-8")
                        break
            elif "body" in payload and "data" in payload["body"]:
                body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
            
            # Truncate body to avoid token limits
            body = body[:500] if len(body) > 500 else body
            
            detailed_emails.append({
                "id": msg["id"],
                "from": headers.get("From", "Unknown"),
                "subject": headers.get("Subject", "No Subject"),
                "date": headers.get("Date", ""),
                "snippet": msg_detail.get("snippet", ""),
                "body": body
            })
        except Exception:
            continue
    
    return detailed_emails


def format_schedule_data(events: List[Dict], tasks: List[Dict], emails: List[Dict]) -> str:
    """Format events, tasks, and emails concisely for Gemini"""
    
    output = "EVENTS:\n"
    if events:
        for event in events[:10]:  # Limit to 10 events
            summary = event.get('summary', 'Untitled')
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date', 'TBD'))
            output += f"- {summary} | {start}\n"
    else:
        output += "None\n"
    
    output += "\nTASKS:\n"
    if tasks:
        for task in tasks[:10]:  # Limit to 10 tasks
            title = task.get('title', 'Untitled')
            due = task.get('due', 'No due date')
            output += f"- {title} | Due: {due}\n"
    else:
        output += "None\n"
    
    output += "\nEMAILS:\n"
    if emails:
        for email in emails[:10]:  # Limit to 10 emails
            sender = email.get('from', 'Unknown')[:30]
            subject = email.get('subject', 'No Subject')[:50]
            output += f"- {sender}: {subject}\n"
    else:
        output += "None\n"
    
    return output


def get_smart_summary(credentials: Credentials, user_context: Optional[str] = None) -> Dict[str, Any]:
    """
    Main function: Fetches all events, tasks & unread emails, then uses Gemini to provide
    intelligent summary and task management recommendations.
    
    Returns a structured response with:
    - Raw data (events, tasks, emails)
    - AI-generated summary
    - Prioritized task order
    - Email-based action items
    - Productivity recommendations
    """
    
    # Fetch all data from Google services
    events = get_all_events(credentials)
    tasks = get_all_tasks(credentials)
    emails = get_unread_emails(credentials)
    
    # Format data for Gemini
    schedule_data = format_schedule_data(events, tasks, emails)
    
    # Gemini system instruction - kept concise to reduce token usage
    system_instruction = """You are a productivity assistant. Be VERY concise.

Provide output in this exact format:

**📧 EMAILS** (max 5 items)
• [Sender]: [Action needed] - [Urgent/Normal]

**📅 MEETINGS** (max 5 items)
• [Time] - [Event name] - [Duration]

**✅ TASKS** (max 5 items)
• [Task] - [Due date if any]

**⚡ TOP 3 PRIORITIES**
1. [Most important action]
2. [Second priority]
3. [Third priority]

Rules:
- One line per item, no extra explanation
- Skip sections if empty
- Max 150 words total"""

    # Build the prompt - kept minimal
    prompt = f"""Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{schedule_data}"""
    
    if user_context:
        prompt += f"\nContext: {user_context}"
    
    # Generate AI response
    config = types.GenerateContentConfig(system_instruction=system_instruction)
    
    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config
    )
    
    ai_summary = response.text or "Unable to generate summary."
    
    return {
        "success": True,
        "generated_at": datetime.now().isoformat(),
        "ai_analysis": ai_summary
    }
