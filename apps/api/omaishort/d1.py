"""Cloudflare D1 over the omaishort-db Worker. Pytest keeps sqlite."""

from __future__ import annotations

import json
import time
from typing import Any

import certifi
import httpx


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
        payload = {"sql": sql, "params": list(params)}
        headers = {
            "content-type": "application/json",
            "user-agent": "omaishort-desktop/0.1",
            "x-omaishort-key": self._key,
        }
        last: Exception | None = None
        for attempt in range(3):
            try:
                response = httpx.post(
                    self._url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                    verify=certifi.where(),
                )
                response.raise_for_status()
                body = response.json()
                break
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                raise RuntimeError(detail or str(exc)) from exc
            except (httpx.TransportError, json.JSONDecodeError) as exc:
                last = exc
                time.sleep(0.4 * (attempt + 1))
        else:
            raise RuntimeError("Cloudflare D1 không phản hồi") from last
        if not body.get("ok"):
            raise RuntimeError(str(body.get("error") or "d1 query failed"))
        rows = body.get("rows") or []
        return D1Result([dict(row) for row in rows])

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None
