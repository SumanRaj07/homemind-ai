"""Tool endpoints: list tools, execute (permission-gated), resolve approvals."""

from __future__ import annotations

from fastapi import APIRouter

from homemind.api.deps import DbDep, StateDep
from homemind.models.schemas import (
    ApprovalResolveRequest,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolInfo,
)

router = APIRouter(tags=["tools"])


@router.get("/tools", response_model=list[ToolInfo])
def list_tools(state: StateDep):
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            permission=t.permission.value,  # type: ignore[arg-type]
            input_schema=t.input_schema,
        )
        for t in state.registry.list_tools()
    ]


@router.post("/tools/{tool_name}/execute", response_model=ToolExecuteResponse)
def execute_tool(
    tool_name: str, payload: ToolExecuteRequest, state: StateDep, db: DbDep
):
    outcome = state.registry.execute(
        db, tool_name, payload.inputs, approval_id=payload.approval_id
    )
    return ToolExecuteResponse(
        status=outcome["status"],  # type: ignore[arg-type]
        approval_id=outcome.get("approval_id"),
        result=outcome.get("result"),
        message=outcome.get("message", ""),
    )


@router.post(
    "/tools/approvals/{approval_id}/resolve", response_model=ToolExecuteResponse
)
def resolve_approval(
    approval_id: str, payload: ApprovalResolveRequest, state: StateDep, db: DbDep
):
    outcome = state.registry.resolve_approval(db, approval_id, payload.approve)
    return ToolExecuteResponse(
        status=outcome["status"],  # type: ignore[arg-type]
        approval_id=outcome.get("approval_id"),
        result=outcome.get("result"),
        message=outcome.get("message", ""),
    )
