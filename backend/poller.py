"""Background polling task — reads inverter every N seconds, stores to DB."""
from __future__ import annotations
import asyncio
import logging
import time
from backend.models import Snapshot
from backend.reader import Reader
from backend.database import Database

logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, reader: Reader, db: Database, interval: float = 5.0) -> None:
        self._reader = reader
        self._db = db
        self._interval = interval
        self._latest: Snapshot | None = None
        self._last_read_ts: float = 0.0
        self._running: bool = False

    @property
    def latest(self) -> Snapshot | None:
        return self._latest

    @property
    def last_read_ts(self) -> float:
        return self._last_read_ts

    async def run(self) -> None:
        self._running = True
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                snapshot = await loop.run_in_executor(None, self._reader.read)
                self._latest = snapshot
                self._last_read_ts = time.time()
                await self._db.insert_reading(snapshot)
            except Exception as exc:
                logger.error("Poll error: %s", exc)
            await asyncio.sleep(self._interval)

    def stop(self) -> None:
        self._running = False
