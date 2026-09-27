"""Read-only public demo guard. Local CLI/API remains fully editable."""

import asyncio
from collections import deque
from pathlib import Path
import time
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse


def protect(app, project, allowed_post, blocked_get=()):
    recent = deque()
    lock = asyncio.Semaphore(2)
    static = Path(__file__).parent / project / "static"
    original = next(r for r in app.routes if getattr(r, "path", None) == "/")
    app.router.routes.remove(original)

    @app.get("/", include_in_schema=False)
    def home():
        html = (static / "index.html").read_text()
        return HTMLResponse(
            html.replace("</head>", '<link rel="stylesheet" href="/public-demo.css"></head>').replace(
                "</body>", '<script src="/public-demo.js" defer></script></body>'
            )
        )

    @app.get("/public-demo.css", include_in_schema=False)
    def styles():
        return FileResponse(Path(__file__).parent / "public-demo.css")

    @app.get("/public-demo.js", include_in_schema=False)
    def script():
        return FileResponse(Path(__file__).parent / "public-demo.js")

    @app.middleware("http")
    async def guard(request, call_next):
        path = request.url.path
        if request.method not in {"GET", "HEAD", "OPTIONS"} and not (
            request.method == "POST" and allowed_post(path)
        ):
            return JSONResponse(
                {
                    "detail": "Public demo: shared data changes are disabled. Clone the source to use the complete workspace."
                },
                status_code=403,
            )
        if any(path == p or path.startswith(p + "/") for p in blocked_get):
            return JSONResponse(
                {"detail": "Private query history is not exposed in the public demo."}, status_code=403
            )
        if request.method == "POST":
            chunks = []
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 16384:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
            now = time.monotonic()
            while recent and recent[0] < now - 60:
                recent.popleft()
            if len(recent) >= 120:
                return JSONResponse(
                    {"detail": "Demo is busy. Please try again in a minute."}, status_code=429
                )
            recent.append(now)
            async with lock:
                return await call_next(request)
        return await call_next(request)

    return app
