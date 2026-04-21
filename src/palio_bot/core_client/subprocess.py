"""Boot `palio_bot.core` as a subprocess for tests and the eval runner.

`CoreProcess` context manager: picks a free port, launches uvicorn
pointed at the given data dir, waits for the server to become reachable,
tears it down on exit.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class CoreProcess:
    def __init__(
        self,
        data_dir: Path,
        port: Optional[int] = None,
        token: Optional[str] = None,
        ready_timeout: float = 10.0,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.port = port or _pick_free_port()
        self.token = token
        self.ready_timeout = ready_timeout
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "CoreProcess":
        self.data_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PALIO_CORE_PORT"] = str(self.port)
        env["PALIO_FILE_PATH"] = str(self.data_dir / "palio.json")
        env["PALIO_GAMES_STATUS_PATH"] = str(self.data_dir / "palio_games_status.json")
        env["LEADERBOARD_FILE_PATH"] = str(self.data_dir / "leaderboard.json")
        env["DATA_DIR"] = str(self.data_dir)
        if self.token:
            env["PALIO_CORE_TOKEN"] = self.token

        logger.info("CoreProcess: starting on port %d (data_dir=%s)", self.port, self.data_dir)
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "palio_bot.core"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        self._wait_ready()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            logger.info("CoreProcess: terminating pid=%d", self._proc.pid)
            self._proc.send_signal(signal.SIGTERM)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("CoreProcess: kill after SIGTERM timeout")
                self._proc.kill()
                self._proc.wait()
        self._proc = None

    def _wait_ready(self) -> None:
        deadline = time.time() + self.ready_timeout
        while time.time() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise RuntimeError(
                    f"palio-core exited with code {self._proc.returncode} before becoming ready"
                )
            try:
                httpx.get(f"{self.base_url}/api/years", timeout=0.5)
                return
            except httpx.HTTPError:
                time.sleep(0.1)
        raise RuntimeError(f"palio-core did not become ready within {self.ready_timeout}s")
