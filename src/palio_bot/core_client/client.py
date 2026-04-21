"""Synchronous HTTP client for palio-core.

Kept sync because the tool layer is sync; localhost round-trips are cheap
enough that blocking briefly inside an awaited tool call is fine.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class CoreClientError(Exception):
    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"core returned {status_code}: {detail}")


class CoreClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8010",
        token: Optional[str] = None,
        timeout: float = 10.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        headers: Dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if http_client is not None:
            self._http = http_client
            self._owned_http = False
        else:
            self._http = httpx.Client(
                base_url=base_url, headers=headers, timeout=timeout
            )
            self._owned_http = True
        self.base_url = base_url

    # ---------- lifecycle ----------

    def close(self) -> None:
        if self._owned_http:
            self._http.close()

    def __enter__(self) -> "CoreClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---------- files (reads) ----------

    def get_file(self, file_name: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/files/{file_name}")

    def get_file_by_year(self, file_name: str, year: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/files/{file_name}/{year}")

    def get_years(self) -> Dict[str, Any]:
        return self._request("GET", "/api/years")

    # ---------- sessions ----------

    def create_session(self, label: str) -> str:
        data = self._request("POST", "/api/sessions", json={"label": label})
        return data["id"]

    def list_sessions(self) -> Dict[str, Any]:
        return self._request("GET", "/api/sessions")

    def acquire(self, session_id: str, file_name: str) -> Dict[str, Any]:
        """Acquire a file for this session; returns {content, version}.

        Raises CoreClientError(409) on lock conflict, (404) on unknown
        session/file.
        """
        return self._request(
            "POST", f"/api/sessions/{session_id}/acquire/{file_name}"
        )

    def put_file(
        self, session_id: str, file_name: str, content: Dict[str, Any]
    ) -> str:
        data = self._request(
            "PUT",
            f"/api/sessions/{session_id}/files/{file_name}",
            json={"content": content},
        )
        return data["version"]

    def commit(self, session_id: str) -> Dict[str, str]:
        data = self._request("POST", f"/api/sessions/{session_id}/commit")
        return data["files"]

    def discard(self, session_id: str) -> None:
        self._request("POST", f"/api/sessions/{session_id}/discard")

    # ---------- admin ----------

    def admin_reset(self, seeds_dir: Optional[str] = None) -> None:
        body: Dict[str, Any] = {}
        if seeds_dir:
            body["seeds_dir"] = seeds_dir
        self._request("POST", "/admin/reset", json=body)

    # ---------- internals ----------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._http.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise CoreClientError(response.status_code, detail)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()
