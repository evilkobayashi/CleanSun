from __future__ import annotations
import logging
import time
import aiosqlite
from backend.models import Snapshot

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str = "history.db"):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          INTEGER NOT NULL,
                source      TEXT,
                solar_w     INTEGER,
                battery_soc INTEGER,
                battery_kw  REAL,
                grid_kw     REAL,
                load_w      INTEGER,
                temp_c      REAL,
                today_kwh   REAL,
                total_kwh   REAL
            )
        """)
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ts ON readings(ts)"
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def insert_reading(self, s: Snapshot) -> None:
        try:
            await self._conn.execute(
                """INSERT INTO readings
                   (ts, source, solar_w, battery_soc, battery_kw,
                    grid_kw, load_w, temp_c, today_kwh, total_kwh)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    s.timestamp, s.source, s.solar.total_w,
                    s.battery.soc_pct, s.battery.power_kw,
                    s.grid.power_kw, s.load.power_w,
                    s.inverter.temp_c, s.energy.today_kwh, s.energy.total_kwh,
                ),
            )
            await self._conn.commit()
        except Exception as exc:
            logger.warning("DB write error: %s", exc)

    async def get_history(self, days: int = 7, bucket: str = "hour") -> list[dict]:
        since = int(time.time()) - days * 86400
        if bucket == "hour":
            divisor = 3600
        elif bucket == "day":
            divisor = 86400
        else:
            divisor = 86400 * 30

        query = f"""
            SELECT
              (ts / {divisor}) * {divisor} AS ts,
              AVG(solar_w)     AS solar_w,
              AVG(battery_soc) AS battery_soc,
              AVG(battery_kw)  AS battery_kw,
              AVG(grid_kw)     AS grid_kw,
              AVG(load_w)      AS load_w,
              AVG(temp_c)      AS temp_c,
              MAX(today_kwh)   AS today_kwh,
              MAX(total_kwh)   AS total_kwh,
              COUNT(*)         AS samples
            FROM readings
            WHERE ts >= ?
            GROUP BY ts / {divisor}
            ORDER BY ts
        """
        async with self._conn.execute(query, (since,)) as cursor:
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]
