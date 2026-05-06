import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, token: str, protected_prefix: str = "/mcp") -> None:
        super().__init__(app)
        self._token = token
        self._prefix = protected_prefix

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(self._prefix):
            return await call_next(request)

        if not self._token:
            return JSONResponse({"error": "server misconfigured"}, status_code=500)

        header = request.headers.get("authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer" or not value:
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        if not secrets.compare_digest(value, self._token):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        return await call_next(request)
