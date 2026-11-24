from fastapi import APIRouter, HTTPException, Query

from ..domain import Task, TaskCreate, TaskUpdate
from ..providers.registry import get_services

router = APIRouter(prefix="/api", tags=["tasks"])

VALID_STATUS = {"todo", "in_progress", "done"}
VALID_PRIORITY = {"low", "medium", "high", "urgent"}


@router.get("/tasks")
def list_tasks(
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    if status and status not in VALID_STATUS | {"open"}:
        raise HTTPException(422, "status must be todo, in_progress, done or open")
    if priority and priority not in VALID_PRIORITY:
        raise HTTPException(422, "priority must be low, medium, high or urgent")
    tasks = get_services().tasks.list_tasks(status=status, priority=priority, search=search)
    return {"tasks": [task.model_dump(mode="json") for task in tasks]}


@router.post("/tasks", status_code=201)
def create_task(payload: TaskCreate) -> Task:
    return get_services().tasks.create_task(payload)


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> Task:
    task = get_services().tasks.get_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdate) -> Task:
    try:
        return get_services().tasks.update_task(task_id, payload)
    except KeyError:
        raise HTTPException(404, "Task not found")


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    try:
        get_services().tasks.delete_task(task_id)
    except KeyError:
        raise HTTPException(404, "Task not found")
    return {"ok": True, "deleted": task_id}
