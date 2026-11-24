from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.workflows import WorkflowError, get_workflow, list_workflows, run_command

router = APIRouter(prefix="/api", tags=["commands"])


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=600)


@router.post("/commands", status_code=201)
def create_command(payload: CommandRequest):
    try:
        return run_command(payload.command)
    except WorkflowError as exc:
        raise HTTPException(exc.status_code, str(exc))


@router.get("/workflows")
def get_workflows(status: str | None = Query(default=None), limit: int = Query(default=30, ge=1, le=100)):
    return {"workflows": list_workflows(status=status, limit=limit)}


@router.get("/workflows/{workflow_id}")
def get_workflow_by_id(workflow_id: str):
    try:
        return get_workflow(workflow_id)
    except WorkflowError as exc:
        raise HTTPException(exc.status_code, str(exc))
