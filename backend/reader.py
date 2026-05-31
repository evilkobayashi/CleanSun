"""Orchestrator: LAN primary → Cloud fallback."""
from __future__ import annotations
import logging
from backend.models import Snapshot
from backend.transports.lan import LANTransport
from backend.transports.cloud import CloudTransport

logger = logging.getLogger(__name__)


class Reader:
    def __init__(
        self,
        lan: LANTransport,
        cloud: CloudTransport | None = None,
        fail_threshold: int = 3,
    ) -> None:
        self._lan = lan
        self._cloud = cloud
        self._threshold = fail_threshold
        self._fail_count: int = 0
        self._using_cloud: bool = False
        self._last_snapshot: Snapshot | None = None

    @property
    def source(self) -> str:
        return "cloud" if self._using_cloud else "lan"

    @property
    def fail_count(self) -> int:
        return self._fail_count

    def read(self) -> Snapshot:
        if self._using_cloud:
            try:
                snap = self._lan.read()
                self._fail_count = 0
                self._using_cloud = False
                logger.info("LAN recovered — switching back from cloud")
                self._last_snapshot = snap
                return snap
            except Exception:
                if self._cloud:
                    snap = self._cloud.read()
                    self._last_snapshot = snap
                    return snap
                raise

        try:
            snap = self._lan.read()
            self._fail_count = 0
            self._last_snapshot = snap
            return snap
        except Exception as exc:
            self._fail_count += 1
            logger.warning(
                "LAN read failed (%d/%d): %s",
                self._fail_count, self._threshold, exc,
            )
            if self._fail_count >= self._threshold and self._cloud:
                logger.warning("Switching to Deye Cloud fallback")
                self._using_cloud = True
                snap = self._cloud.read()
                self._last_snapshot = snap
                return snap
            if self._last_snapshot is not None:
                return self._last_snapshot.model_copy(
                    update={"stale": True, "source": "stale"}
                )
            raise
