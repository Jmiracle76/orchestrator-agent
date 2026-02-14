from __future__ import annotations

from flask.testing import FlaskClient


def csrf_headers(client: FlaskClient, path: str = "/") -> dict[str, str]:
    """Return headers with a valid CSRF token for the given test client."""
    client.get(path)
    token = client.get_cookie("csrf_token")
    value = getattr(token, "value", token)
    assert value, "CSRF token cookie missing from client"
    return {"X-CSRFToken": value}
