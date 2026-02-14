from __future__ import annotations

from flask import Blueprint, jsonify, request

from web.session_state import clear_workflow_state, ensure_workflow_state, update_workflow_state

session_api_bp = Blueprint("session_api", __name__, url_prefix="/api/session")


@session_api_bp.before_app_request
def ensure_state_exists() -> None:
    ensure_workflow_state()


@session_api_bp.get("/workflow")
def get_workflow_state():
    return jsonify(ensure_workflow_state())


@session_api_bp.post("/workflow")
def set_workflow_state():
    payload = request.get_json(silent=True) or {}
    state = update_workflow_state(payload)
    return jsonify(state)


@session_api_bp.delete("/workflow")
def clear_workflow():
    clear_workflow_state()
    return jsonify({"cleared": True})
