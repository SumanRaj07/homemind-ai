"""Tool registry with permission enforcement and audit logging.

Execution flow:
  1. ``execute()`` looks up the tool and validates the caller asked for a
     known tool.
  2. Read tools run immediately (with a timeout guard).
  3. Write tools without a valid approval return ``approval_required`` and a
     pending approval id; the caller must POST the approval decision first.
  4. Every attempt is written to the ``tool_audit`` table.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from homemind.config.settings import Settings
from homemind.storage.models import ToolAudit
from homemind.tools.permissions import Permission, requires_approval


@dataclass
class Tool:
    name: str
    description: str
    permission: Permission
    input_schema: dict[str, Any]
    handler: Callable[[Session, Settings, dict[str, Any]], dict[str, Any]]
    timeout_s: float = 30.0


@dataclass
class PendingApproval:
    id: str
    tool_name: str
    inputs: dict[str, Any]
    created_at: float = field(default_factory=time.time)


class ToolRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tools: dict[str, Tool] = {}
        self._pending: dict[str, PendingApproval] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    # -- audit ------------------------------------------------------------ #
    def _audit(
        self,
        db: Session,
        tool_name: str,
        permission: Permission,
        status: str,
        inputs: dict[str, Any],
    ) -> None:
        summary = json.dumps(inputs, default=str)[:500]
        db.add(
            ToolAudit(
                tool_name=tool_name,
                permission=permission.value,
                status=status,
                input_summary=summary,
            )
        )
        db.flush()

    # -- execution -------------------------------------------------------- #
    def execute(
        self,
        db: Session,
        tool_name: str,
        inputs: dict[str, Any],
        *,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        tool = self.get(tool_name)
        if tool is None:
            return {"status": "denied", "message": f"unknown tool: {tool_name}"}

        if requires_approval(tool.permission):
            pending = self._pending.get(approval_id or "")
            if pending is None or pending.tool_name != tool_name:
                approval = PendingApproval(
                    id=uuid.uuid4().hex, tool_name=tool_name, inputs=dict(inputs)
                )
                self._pending[approval.id] = approval
                self._audit(db, tool_name, tool.permission, "approval_required", inputs)
                return {
                    "status": "approval_required",
                    "approval_id": approval.id,
                    "message": (
                        f"Tool '{tool_name}' requires explicit user approval "
                        "before it can run."
                    ),
                }
            # Approval granted — consume it (single use).
            del self._pending[approval_id or ""]
            inputs = pending.inputs
            self._audit(db, tool_name, tool.permission, "approved", inputs)

        started = time.monotonic()
        try:
            result = tool.handler(db, self.settings, dict(inputs))
        except Exception as exc:  # noqa: BLE001 - surfaced as tool error
            self._audit(db, tool_name, tool.permission, "denied", inputs)
            return {"status": "denied", "message": f"tool error: {exc}"}
        elapsed = time.monotonic() - started
        if elapsed > tool.timeout_s:
            self._audit(db, tool_name, tool.permission, "denied", inputs)
            return {"status": "denied", "message": "tool timed out"}
        self._audit(db, tool_name, tool.permission, "executed", inputs)
        return {"status": "executed", "result": result, "message": ""}

    def resolve_approval(
        self, db: Session, approval_id: str, approve: bool
    ) -> dict[str, Any]:
        pending = self._pending.get(approval_id)
        if pending is None:
            return {"status": "denied", "message": "approval not found or expired"}
        tool = self.get(pending.tool_name)
        permission = tool.permission if tool else Permission.WRITE
        if not approve:
            del self._pending[approval_id]
            self._audit(db, pending.tool_name, permission, "denied", pending.inputs)
            return {"status": "denied", "message": "approval rejected by user"}
        # Re-enter execute() with the now-valid approval id.
        return self.execute(db, pending.tool_name, pending.inputs, approval_id=approval_id)


def build_default_registry(settings: Settings) -> ToolRegistry:
    from homemind.tools import builtin  # local import: avoids cycles

    registry = ToolRegistry(settings)
    for spec in builtin.BUILTIN_TOOLS:
        registry.register(
            Tool(
                name=spec["name"],
                description=spec["description"],
                permission=Permission(spec["permission"]),
                input_schema=spec["input_schema"],
                handler=spec["handler"],
            )
        )
    return registry
