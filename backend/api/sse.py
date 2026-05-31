"""SSE endpoint — pushes snapshot every 5 seconds."""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse


def create_sse_router() -> APIRouter:
    router = APIRouter()

    @router.get("/events")
    async def events(request: Request):
        poller = request.app.state.poller

        async def stream():
            while True:
                if await request.is_disconnected():
                    break
                if poller.latest is not None:
                    data = poller.latest.model_dump_json()
                    yield f"event: update\ndata: {data}\n\n"
                await asyncio.sleep(5)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
