"""
Google Tasks API Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from googleapiclient.errors import HttpError
from auth.router import get_credentials
from google_services.tasks_service import (
    list_task_lists,
    list_tasks,
    create_task,
    complete_task,
    uncomplete_task,
    update_task,
    delete_task,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskCreate(BaseModel):
    title: str
    notes: str = ""
    task_list_id: str = "@default"
    status: str = "needsAction"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    task_list_id: str = "@default"


@router.get("/lists")
def get_task_lists():
    """Get all task lists"""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated. Visit /auth/login first.")
    try:
        return list_task_lists(credentials)
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.get("/")
def get_tasks(task_list_id: str = "@default", show_completed: bool = True):
    """Get all tasks in a task list, including completed tasks"""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated. Visit /auth/login first.")
    try:
        tasks = list_tasks(credentials, task_list_id, show_completed)
        return {"tasks": tasks}
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.post("/")
def add_task(task: TaskCreate):
    """Create a new task"""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated. Visit /auth/login first.")
    try:
        return create_task(
            credentials,
            title=task.title,
            notes=task.notes,
            task_list_id=task.task_list_id,
            status=task.status
        )
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.put("/{task_id}")
def modify_task(task_id: str, task: TaskUpdate):
    """Update a task's properties"""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated. Visit /auth/login first.")
    try:
        return update_task(
            credentials,
            task_id=task_id,
            task_list_id=task.task_list_id,
            title=task.title,
            notes=task.notes,
            status=task.status
        )
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.put("/{task_id}/complete")
def mark_complete(task_id: str, task_list_id: str = "@default"):
    """Mark a task as completed"""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated. Visit /auth/login first.")
    try:
        return complete_task(credentials, task_id, task_list_id)
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.put("/{task_id}/uncomplete")
def mark_uncomplete(task_id: str, task_list_id: str = "@default"):
    """Mark a task as not completed (reopen)"""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated. Visit /auth/login first.")
    try:
        return uncomplete_task(credentials, task_id, task_list_id)
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))


@router.delete("/{task_id}")
def remove_task(task_id: str, task_list_id: str = "@default"):
    """Delete a task"""
    credentials = get_credentials()
    if not credentials:
        raise HTTPException(status_code=401, detail="User not authenticated. Visit /auth/login first.")
    try:
        return delete_task(credentials, task_id, task_list_id)
    except HttpError as e:
        raise HTTPException(status_code=e.resp.status, detail=str(e))
