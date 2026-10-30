"""ASGI byte/time budgets apply before multipart parsing, including chunked bodies."""

import asyncio

from starlette.responses import JSONResponse

MAX_BODY = 20 * 1024 * 1024 + 65536


class SecurityEnvelope:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        path = scope.get("path", "")
        maximum = MAX_BODY if path.endswith("/upload") else 65536
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0 or length > maximum:
                raise ValueError
        except ValueError:
            return await JSONResponse({"detail": "Request body exceeds limit."}, 413)(
                scope, receive, send
            )
        # Buffer only a bounded body, so even chunked uploads cannot exhaust the parser.
        messages, total = [], 0
        try:
            async with asyncio.timeout(20):
                while True:
                    message = await receive()
                    total += len(message.get("body", b""))
                    if total > maximum:
                        return await JSONResponse(
                            {"detail": "Request body exceeds limit."}, 413
                        )(scope, receive, send)
                    messages.append(message)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await JSONResponse({"detail": "Request body timed out."}, 408)(
                scope, receive, send
            )
        iterator = iter(messages)

        async def bounded_receive():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()

        async def safe_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                ]
            await send(message)

        await self.app(scope, bounded_receive, safe_send)
