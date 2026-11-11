"""CSRF protection middleware for state-changing browser requests.

Finora is a single-user, server-rendered local application. A CSRF token is
generated per session and exposed to the client via the ``X-CSRF-Token``
response header and a ``csrf-token`` meta tag in templates. State-changing
POST/PUT/PATCH/DELETE requests must echo the token back in the
``X-CSRF-Token`` header; otherwise they are rejected with 403.

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


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session = request.session
        token = session.get("csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token

        if request.method in MUTATING_METHODS and not self._is_exempt(request.url.path):
            header = request.headers.get("x-csrf-token")
            if not header or not secrets.compare_digest(header, token):
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
        import secrets as _secrets

        token = _secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token
