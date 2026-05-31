"""REST API routes."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/snapshot")
    async def get_snapshot(request: Request):
        poller = request.app.state.poller
        if poller.latest is None:
            raise HTTPException(503, detail="No data yet — inverter not polled")
        return poller.latest

    @router.get("/history")
    async def get_history(request: Request, days: int = 7, bucket: str = "hour"):
        if bucket not in ("hour", "day", "month"):
            raise HTTPException(400, detail="bucket must be hour, day, or month")
        db = request.app.state.db
        rows = await db.get_history(days=days, bucket=bucket)
        return {"days": days, "bucket": bucket, "rows": rows}

    @router.get("/alerts")
    async def get_alerts(request: Request):
        poller = request.app.state.poller
        if poller.latest is None:
            return {"alerts": []}
        return {"alerts": poller.latest.alerts}

    @router.get("/status")
    async def get_status(request: Request):
        poller = request.app.state.poller
        reader = request.app.state.reader
        return {
            "source": reader.source,
            "last_read_ts": poller.last_read_ts,
            "fail_count": reader.fail_count,
            "has_data": poller.latest is not None,
        }

    return router
