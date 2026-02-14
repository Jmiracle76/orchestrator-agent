from datetime import datetime

from flask import Blueprint, render_template

document_bp = Blueprint("document", __name__, url_prefix="/documents")


@document_bp.route("/")
def list_documents():
    documents = [
        {"name": "requirements.md", "status": "in-progress", "updated_at": datetime.utcnow()},
        {"name": "architecture.md", "status": "review", "updated_at": datetime.utcnow()},
    ]
    return render_template(
        "documents/list.html", documents=documents, title="Documents overview"
    )
