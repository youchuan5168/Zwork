"""安全响应头、请求编号、有限请求体和浏览器来源边界。"""

from uuid import uuid4
from starlette.requests import Request
from starlette.responses import JSONResponse


class SecurityMiddleware:
    def __init__(self, app, config):
        self.app, self.config = app, config

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def safe_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-request-id", request_id.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                    ]
                )
                if scope["path"].startswith("/api"):
                    headers = [(k, v) for k, v in headers if k.lower() != b"cache-control"]
                    headers.append((b"cache-control", b"no-store"))
                if self.config.app_env == "production":
                    headers.append(
                        (
                            b"content-security-policy",
                            b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                        )
                    )
                    if scope["scheme"] == "https":
                        headers.append((b"strict-transport-security", b"max-age=31536000"))
                message = {**message, "headers": headers}
            await send(message)

        write = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        if write and scope["path"].startswith("/api/"):
            origin = request.headers.get("origin")
            allowed = {str(request.base_url).rstrip("/"), *self.config.cors_origins}
            if origin is not None and origin not in allowed:
                return await JSONResponse({"detail": "不允许的请求来源"}, 403)(
                    scope, receive, safe_send
                )
            path = scope["path"]
            if path.startswith("/api/auth/"):
                limit = 8192
            elif path.startswith("/api/profile/documents/") and path.endswith("/import"):
                limit = 5_100_000  # 5 MB file plus bounded multipart metadata.
            else:
                limit = 1024 * 1024
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return await JSONResponse({"detail": "无效的请求长度"}, 400)(
                    scope, receive, safe_send
                )
            if length < 0 or length > limit:
                return await JSONResponse({"detail": "请求体过大"}, 413)(scope, receive, safe_send)
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > limit:
                    return await JSONResponse({"detail": "请求体过大"}, 413)(
                        scope, receive, safe_send
                    )
                if not message.get("more_body", False):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            return await self.app(scope, replay, safe_send)
        return await self.app(scope, receive, safe_send)
