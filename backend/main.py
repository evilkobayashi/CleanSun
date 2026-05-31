"""FastAPI application entry point."""
from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import Settings
from backend.database import Database
from backend.transports.lan import LANTransport
from backend.transports.cloud import CloudTransport
from backend.reader import Reader
from backend.poller import Poller
from backend.api.routes import create_router
from backend.api.sse import create_sse_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Settings.from_file()
    db = Database(cfg.server.db_path)
    await db.connect()

    lan = LANTransport(
        ip=cfg.lan.datalogger_ip,
        serial=cfg.lan.datalogger_serial,
        port=cfg.lan.port,
        battery_kwh=cfg.lan.battery_kwh,
    )

    cloud: CloudTransport | None = None
    if cfg.cloud.enabled and cfg.cloud.app_id:
        cloud = CloudTransport(
            app_id=cfg.cloud.app_id,
            app_secret=cfg.cloud.app_secret,
            email=cfg.cloud.email,
            password=cfg.cloud.password,
            device_sn=cfg.cloud.device_sn,
            battery_kwh=cfg.lan.battery_kwh,
        )

    reader = Reader(lan=lan, cloud=cloud, fail_threshold=cfg.lan.fail_threshold)
    poller = Poller(reader=reader, db=db, interval=cfg.lan.poll_seconds)

    app.state.db = db
    app.state.reader = reader
    app.state.poller = poller

    task = asyncio.create_task(poller.run())
    yield

    poller.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await db.close()


def create_app() -> FastAPI:
    application = FastAPI(title="CleanSun v2", version="2.0.0", lifespan=lifespan)
    application.include_router(create_router(), prefix="/api")
    application.include_router(create_sse_router(), prefix="/api")

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        assets_dir = os.path.join(static_dir, "assets")
        if os.path.exists(assets_dir):
            application.mount(
                "/assets", StaticFiles(directory=assets_dir), name="assets"
            )

        @application.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            return FileResponse(os.path.join(static_dir, "index.html"))

    return application


app = create_app()
