from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.execution import decide_action, decide_all, execute_workflow
from ..services.workflows import WorkflowError, list_workflows

router = APIRouter(prefix="/api", tags=["approvals"])


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    action_ids: list[str] | None = None


def _handle(callable_, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except WorkflowError as exc:
        raise HTTPException(exc.status_code, str(exc))


@router.get("/approvals")
def approvals():
    pending = list_workflows(status="pending", limit=30)
    recent = [workflow for workflow in list_workflows(limit=40) if workflow.status != "pending_approval"][:15]
    return {"pending": pending, "recent": recent}


@router.post("/approvals/{workflow_id}/actions/{action_id}/decision")
def decide_single(workflow_id: str, action_id: str, payload: DecisionRequest):
    return _handle(decide_action, workflow_id, action_id, payload.decision)


@router.post("/approvals/{workflow_id}/decision")
def decide_bulk(workflow_id: str, payload: DecisionRequest):
    return _handle(decide_all, workflow_id, payload.decision, payload.action_ids)


@router.post("/approvals/{workflow_id}/execute")
def execute(workflow_id: str):
    return _handle(execute_workflow, workflow_id)
