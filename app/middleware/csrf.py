"""CSRF protection middleware for state-changing browser requests.

Finora is a single-user, server-rendered local application. A CSRF token is
generated per session and exposed to the client via:

* the ``X-CSRF-Token`` response header (for fetch/JS clients), and
* a hidden ``csrf_token`` input field in every server-rendered form.

State-changing POST/PUT/PATCH/DELETE requests must echo the token back either
in the ``X-CSRF-Token`` header or in the ``csrf_token`` form field; otherwise
they are rejected with 403.

Same-origin browser navigation/form submissions are allowed because the
browser sets ``Sec-Fetch-Site: same-origin`` automatically and a cross-site
attacker cannot forge that header.

SessionMiddleware must be added before this middleware so that
``request.session`` is available.
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT_PATHS = {"/api/import-export/import", "/api/import-export/preview"}


def _tokens_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return secrets.compare_digest(a, b)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session = request.session
        token = session.get("csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token

        if request.method in MUTATING_METHODS and not self._is_exempt(request.url.path):
            # 1. Custom header (fetch / JS clients).
            header = request.headers.get("x-csrf-token")
            if _tokens_match(header, token):
                response = await call_next(request)
                response.headers["X-CSRF-Token"] = token
                return response

            # 2. Hidden form field (server-rendered HTML forms).
            form_token = None
            content_type = request.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type:
                try:
                    form = await request.form()
                    form_token = form.get("csrf_token")
                except Exception:
                    # Malformed form body: treat as missing token and reject.
                    form_token = None
            if form_token and _tokens_match(form_token, token):
                response = await call_next(request)
                response.headers["X-CSRF-Token"] = token
                return response

            return Response("CSRF token missing or invalid", status_code=403)

        response = await call_next(request)
        response.headers["X-CSRF-Token"] = token
        return response

    @staticmethod
    def _is_exempt(path: str) -> bool:
        return any(path.startswith(p) for p in EXEMPT_PATHS)


def generate_csrf_token(request: Request) -> str:
    session = request.session
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token
