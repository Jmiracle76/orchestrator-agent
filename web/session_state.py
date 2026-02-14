from __future__ import annotations

from typing import Any, Dict, List, MutableMapping

from flask import session

WorkflowState = Dict[str, Any]


def ensure_workflow_state() -> WorkflowState:
    stored = session.get("workflow_state")
    base: WorkflowState = {
        "current_doc": None,
        "workflow_params": {},
        "execution_history": [],
    }

    if isinstance(stored, MutableMapping):
        base["current_doc"] = stored.get("current_doc")
        params = stored.get("workflow_params")
        history = stored.get("execution_history")
        base["workflow_params"] = params if isinstance(params, MutableMapping) else {}
        base["execution_history"] = history if isinstance(history, List) else []

    session["workflow_state"] = base
    return base


def update_workflow_state(updates: WorkflowState) -> WorkflowState:
    state = ensure_workflow_state()
    for key in ("current_doc", "workflow_params", "execution_history"):
        if key not in updates:
            continue
        value = updates[key]
        if key == "workflow_params" and not isinstance(value, MutableMapping):
            continue
        if key == "execution_history" and not isinstance(value, List):
            continue
        state[key] = value
    session["workflow_state"] = state
    session.modified = True
    return state


def clear_workflow_state() -> None:
    session.pop("workflow_state", None)
    session.modified = True
