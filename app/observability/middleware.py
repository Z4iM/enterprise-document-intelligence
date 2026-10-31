"""Server-generated trace IDs; never inspect bodies, queries, headers or identities."""

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.observability.tracing import collection, persist, span


class TelemetryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Incoming correlation headers are untrusted, not adopted as trace identities.
        with collection() as collector:
            status, started = 500, False

            async def traced_send(message):
                nonlocal status, started
                if message["type"] == "http.response.start":
                    status, started = message["status"], True
                    message["headers"] = [
                        (key, value)
                        for key, value in message.get("headers", [])
                        if key.lower() != b"x-request-id"
                    ] + [(b"x-request-id", collector.trace_id.encode("ascii"))]
                await send(message)

            with span("http.request") as item:
                try:
                    await self.app(scope, receive, traced_send)
                except Exception:
                    status, item.status = 500, "error"
                    if started:
                        raise
                    await JSONResponse(
                        {"detail": "Request failed.", "request_id": collector.trace_id},
                        500,
                    )(scope, receive, traced_send)
                finally:
                    item.measurements["http_status"] = status
                    if status >= 400:
                        item.status = "denied" if status in {401, 403, 404} else "error"
            # Collector mutations made in FastAPI's thread pool remain visible here.
            application = scope.get("app")
            sessions = getattr(
                getattr(application, "state", None), "resource_session_factory", None
            )
            if sessions and not scope.get("path", "").startswith("/operations"):
                await run_in_threadpool(persist, collector, sessions)
