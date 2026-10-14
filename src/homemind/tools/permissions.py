"""Tool permission model.

Every tool declares a permission level:
  - ``read``:  safe, side-effect free; executes immediately.
  - ``write``: consequential (creates, modifies or deletes state); requires
               explicit user approval before execution.

The registry enforces this: a write tool called without a valid approval id
returns ``approval_required`` instead of executing. Nothing model-generated is
ever executed automatically — the model cannot call tools at all; only the
user (via UI/API) can.
"""

from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    READ = "read"
    WRITE = "write"


def requires_approval(permission: Permission) -> bool:
    return permission == Permission.WRITE
