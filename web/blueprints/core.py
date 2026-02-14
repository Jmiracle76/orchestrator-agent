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


@core_bp.route("/style-guide")
def style_guide():
    tokens = [
        {"name": "Primary", "value": "#6366f1", "usage": "Affordances for main actions and focus states", "var": "--color-primary"},
        {"name": "Accent", "value": "#22d3ee", "usage": "Progressive disclosure, hover treatments, subtle gradients", "var": "--color-accent"},
        {"name": "Success", "value": "#22c55e", "usage": "Positive states, ready/complete banners, confirmation buttons", "var": "--color-success"},
        {"name": "Warning", "value": "#f59e0b", "usage": "Caution banners, pending review indicators", "var": "--color-warning"},
        {"name": "Danger", "value": "#ef4444", "usage": "Destructive actions with confirmation steps", "var": "--color-danger"},
        {"name": "Surface", "value": "#0f172a", "usage": "Shell background; pair with 0.8-0.9 opacity overlays", "var": "--color-surface"},
        {"name": "Panel", "value": "#0b1224", "usage": "Cards, dialogs, and navigation bars", "var": "--color-panel"},
        {"name": "Border", "value": "#1e293b", "usage": "Hairlines, input outlines, divider strokes", "var": "--color-border"},
    ]
    layout_specs = [
        {"label": "Content width", "guideline": "Use max-w-5xl/7xl with 24-32px gutters; collapse to single column below 960px."},
        {"label": "Spacing rhythm", "guideline": "Base unit is 4px. Stack sections with 16/24/32px steps; use 12px for tight controls."},
        {"label": "Elevation", "guideline": "Use subtle ring + shadow at rest; deepen shadow and saturation on hover/focus."},
        {"label": "Typography", "guideline": "Space Grotesk for display/body, Plex Mono for code/meta. Keep line-height at 1.5 for copy."},
    ]
    return render_template(
        "style_guide.html",
        title="UI Component Library",
        tokens=tokens,
        layout_specs=layout_specs,
    )
