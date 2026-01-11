"""
Google Tasks Service
Integrates with Google Tasks API
"""
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime


def get_tasks_service(credentials: Credentials):
    """Create Google Tasks service instance"""
    return build("tasks", "v1", credentials=credentials)


def list_task_lists(credentials: Credentials):
    """List all task lists for the user"""
    service = get_tasks_service(credentials)
    results = service.tasklists().list(maxResults=10).execute()
    return results.get("items", [])


def list_tasks(credentials: Credentials, task_list_id: str = "@default", show_completed: bool = True):
    """List all tasks in a task list, including completed tasks"""
    service = get_tasks_service(credentials)
    results = service.tasks().list(
        tasklist=task_list_id,
        showCompleted=show_completed,
        showHidden=True
    ).execute()
    return results.get("items", [])


def create_task(credentials: Credentials, title: str, notes: str = "", task_list_id: str = "@default", status: str = "needsAction"):
    """Create a new task"""
    service = get_tasks_service(credentials)
    
    task = {
        "title": title,
        "notes": notes,
        "status": status,
    }
    
    result = service.tasks().insert(tasklist=task_list_id, body=task).execute()
    return result


def complete_task(credentials: Credentials, task_id: str, task_list_id: str = "@default"):
    """Mark a task as completed"""
    service = get_tasks_service(credentials)
    
    task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
    task["status"] = "completed"
    task["completed"] = datetime.utcnow().isoformat() + "Z"
    
    result = service.tasks().update(tasklist=task_list_id, task=task_id, body=task).execute()
    return result


def uncomplete_task(credentials: Credentials, task_id: str, task_list_id: str = "@default"):
    """Mark a task as not completed (reopen)"""
    service = get_tasks_service(credentials)
    
    task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
    task["status"] = "needsAction"
    if "completed" in task:
        del task["completed"]
    
    result = service.tasks().update(tasklist=task_list_id, task=task_id, body=task).execute()
    return result


def update_task(credentials: Credentials, task_id: str, task_list_id: str = "@default", title: str = None, notes: str = None, status: str = None):
    """Update a task's properties"""
    service = get_tasks_service(credentials)
    
    task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
    
    if title is not None:
        task["title"] = title
    if notes is not None:
        task["notes"] = notes
    if status is not None:
        task["status"] = status
        if status == "completed":
            task["completed"] = datetime.utcnow().isoformat() + "Z"
        elif "completed" in task:
            del task["completed"]
    
    result = service.tasks().update(tasklist=task_list_id, task=task_id, body=task).execute()
    return result


def delete_task(credentials: Credentials, task_id: str, task_list_id: str = "@default"):
    """Delete a task"""
    service = get_tasks_service(credentials)
    service.tasks().delete(tasklist=task_list_id, task=task_id).execute()
    return {"message": "Task deleted successfully"}
