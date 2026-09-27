"""Cloudflare D1 over the omaishort-db Worker. Pytest keeps sqlite."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class D1Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._index = 0

    def fetchone(self) -> dict[str, Any] | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> list[dict[str, Any]]:
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return rows


class D1Connection:
    def __init__(self, url: str, key: str) -> None:
        self._url = url.rstrip("/") + "/query"
        self._key = key

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> D1Result:
        body = json.dumps({"sql": sql, "params": list(params)}).encode("utf-8")
        request = urllib.request.Request(
            self._url,
            data=body,
            headers={
                "content-type": "application/json",
                "user-agent": "omaishort-desktop/0.1",
                "x-omaishort-key": self._key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(detail or exc.reason) from exc
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "d1 query failed"))
        rows = payload.get("rows") or []
        return D1Result([dict(row) for row in rows])

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None
