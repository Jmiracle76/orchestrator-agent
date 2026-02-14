from flask import Blueprint, render_template

core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def index():
    highlights = [
        {"title": "Document-driven orchestration", "body": "Control workflows directly from markdown with review gates and LLM policy enforcement."},
        {"title": "Blueprint-ready", "body": "Health, document, and core routes are organized for fast backend integration."},
        {"title": "Operational visibility", "body": "Structured logging to console and file keeps deployments observable from day one."},
    ]
    return render_template("index.html", highlights=highlights, title="Orchestrator Console")
