"""Muse Hatch Noise client — clean-room port of videoai museHatchClient contracts."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import struct
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MUSE = "https://muse.ai"
HATCH = "wss://hatch.metaaivm.com/v1/noise"
MAX_FRAME = 65489


class MuseHatchError(Exception):
    def __init__(self, code: str, message: str, *, recoverable: bool = False):
        super().__init__(message)
        self.code = code
        self.recoverable = recoverable


def _varint(value: int) -> bytes:
    n = value & ((1 << 64) - 1)
    out = bytearray()
    while n > 127:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def _read_varint(buf: bytes, state: dict[str, int]) -> int:
    value = 0
    shift = 0
    while state["pos"] < len(buf):
        b = buf[state["pos"]]
        state["pos"] += 1
        value |= (b & 127) << shift
        if not (b & 128):
            return value
        shift += 7
        if shift > 70:
            break
    raise MuseHatchError("PROTOCOL", "Invalid Muse protocol varint.")


def _field(num: int, wire: int, value: int | bytes) -> bytes:
    head = _varint((num << 3) | wire)
    if wire == 0:
        return head + _varint(int(value))
    raw = value if isinstance(value, (bytes, bytearray)) else bytes(value)
    return head + _varint(len(raw)) + raw


def _fstr(n: int, s: str) -> bytes:
    return _field(n, 2, s.encode("utf-8"))


def _fbytes(n: int, b: bytes) -> bytes:
    return _field(n, 2, b)


def _fbool(n: int, b: bool) -> bytes:
    return _field(n, 0, 1 if b else 0)


def _parse_fields(buf: bytes) -> list[tuple[int, int, Any]]:
    out: list[tuple[int, int, Any]] = []
    state = {"pos": 0}
    while state["pos"] < len(buf):
        tag = _read_varint(buf, state)
        n = tag >> 3
        w = tag & 7
        if w == 0:
            raw = _read_varint(buf, state)
            v: Any = raw if n == 1 else int(raw)
        elif w == 2:
            length = _read_varint(buf, state)
            if length < 0 or state["pos"] + length > len(buf):
                raise MuseHatchError("PROTOCOL", "Invalid Muse protocol field length.")
            v = buf[state["pos"] : state["pos"] + length]
            state["pos"] += length
        elif w in (1, 5):
            length = 8 if w == 1 else 4
            v = buf[state["pos"] : state["pos"] + length]
            state["pos"] += length
        else:
            raise MuseHatchError("PROTOCOL", f"Unsupported Muse protocol wire type {w}.")
        out.append((n, w, v))
    return out


def _nonce12(n: int) -> bytes:
    out = bytearray(12)
    out[4:12] = struct.pack(">Q", n & ((1 << 64) - 1))
    return bytes(out)


def _hkdf(ck: bytes, ikm: bytes, count: int = 2) -> list[bytes]:
    temp = hmac.new(ck, ikm, hashlib.sha256).digest()
    one = hmac.new(temp, bytes([1]), hashlib.sha256).digest()
    two = hmac.new(temp, one + bytes([2]), hashlib.sha256).digest()
    if count == 2:
        return [one, two]
    three = hmac.new(temp, two + bytes([3]), hashlib.sha256).digest()
    return [one, two, three]


def _sha(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def _keypair() -> tuple[bytes, bytes]:
    priv = X25519PrivateKey.generate()
    pub = priv.public_key().public_bytes_raw()
    return pub, priv.private_bytes_raw()


def _dh(priv_raw: bytes, pub_raw: bytes) -> bytes:
    priv = X25519PrivateKey.from_private_bytes(priv_raw)
    pub = X25519PublicKey.from_public_bytes(pub_raw)
    return priv.exchange(pub)


def _seal(key: bytes, nonce: bytes, ad: bytes, body: bytes) -> bytes:
    return AESGCM(key).encrypt(nonce, body, ad)


def _open(key: bytes, nonce: bytes, ad: bytes, body: bytes) -> bytes:
    return AESGCM(key).decrypt(nonce, body, ad)


class NoiseHandshake:
    def __init__(self) -> None:
        proto = b"Noise_XX_25519_AESGCM_SHA256"
        self.h = proto + bytes(32 - len(proto)) if len(proto) <= 32 else _sha(proto)
        self.ck = bytes(self.h)
        self.k: bytes | None = None
        self.n = 0
        self.phase = 1
        self.e_pub = b""
        self.e_priv = b""
        self.re = b""
        self.rs = b""
        self.s_pub = b""
        self.s_priv = b""
        self.mix_hash(b"")

    def mix_hash(self, x: bytes) -> None:
        self.h = _sha(self.h + x)

    def mix_key(self, x: bytes) -> None:
        self.ck, self.k = _hkdf(self.ck, x)
        self.n = 0

    def encrypt_hash(self, x: bytes) -> bytes:
        out = _seal(self.k, _nonce12(self.n), self.h, x) if self.k else x
        if self.k:
            self.n += 1
        self.mix_hash(out)
        return out

    def decrypt_hash(self, x: bytes) -> bytes:
        out = _open(self.k, _nonce12(self.n), self.h, x) if self.k else x
        if self.k:
            self.n += 1
        self.mix_hash(x)
        return out

    def message1(self) -> bytes:
        if self.phase != 1:
            raise MuseHatchError("PROTOCOL", "Invalid Muse handshake state.")
        self.e_pub, self.e_priv = _keypair()
        self.mix_hash(self.e_pub)
        import os

        payload = _fbytes(1, os.urandom(32))
        self.phase = 2
        return self.e_pub + self.encrypt_hash(payload)

    def message2(self, msg: bytes) -> bytes:
        if self.phase != 2 or len(msg) < 96:
            raise MuseHatchError("PROTOCOL", "Muse WebSocket sent an invalid Noise handshake.")
        self.re = msg[:32]
        self.mix_hash(self.re)
        self.mix_key(_dh(self.e_priv, self.re))
        self.rs = self.decrypt_hash(msg[32:80])
        self.mix_key(_dh(self.e_priv, self.rs))
        payload = self.decrypt_hash(msg[80:])
        self.phase = 3
        return payload

    def message3(self) -> tuple[bytes, bytes, bytes]:
        if self.phase != 3:
            raise MuseHatchError("PROTOCOL", "Invalid Muse handshake state.")
        self.s_pub, self.s_priv = _keypair()
        encrypted = self.encrypt_hash(self.s_pub)
        self.mix_key(_dh(self.s_priv, self.re))
        msg = encrypted + self.encrypt_hash(b"")
        tx, rx = _hkdf(self.ck, b"")
        self.phase = 4
        return msg, tx, rx


def _nonce_chunk(chunk_id: int, index: int, total: int, payload: bytes) -> bytes:
    return b"".join(
        [
            _field(1, 0, chunk_id),
            _field(2, 0, index),
            _field(3, 0, total),
            _fbytes(4, payload),
        ]
    )


def _split_payload(payload: bytes) -> list[bytes]:
    total = max(1, (len(payload) + MAX_FRAME - 1) // MAX_FRAME)
    if total > 256:
        raise MuseHatchError("PROTOCOL", f"Muse payload too large for Noise framing: {total} chunks")
    import os

    chunk_id = int.from_bytes(os.urandom(8), "little", signed=True)
    while chunk_id == 0:
        chunk_id = int.from_bytes(os.urandom(8), "little", signed=True)
    frames = []
    for i in range(total):
        frames.append(_nonce_chunk(chunk_id, i, total, payload[i * MAX_FRAME : (i + 1) * MAX_FRAME]))
    return frames


def _service_envelope(service_frame: bytes) -> bytes:
    return _field(1, 0, 0) + _fbytes(2, service_frame)


def _app_request(method: str, path: str, body: bytes, locale: str = "en-US") -> bytes:
    headers = []
    if method.upper() != "GET":
        headers.append(("Content-Type", "application/json"))
    headers.extend(
        [
            ("x-request-id", str(uuid.uuid4())),
            ("x-app-id", "hatch-web"),
            ("Accept-Language", locale),
        ]
    )
    packed = [_fstr(1, method), _fstr(2, path)]
    for k, v in headers:
        packed.append(_fbytes(3, _fstr(1, k) + _fstr(2, v)))
    if body:
        packed.append(_fbytes(4, body))
    packed.append(_fbool(5, True))
    return b"".join(packed)


@dataclass
class MuseImage:
    name: str
    mime_type: str
    data: bytes


def muse_items(images: list[MuseImage], prompt: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for img in images:
        items.append(
            {
                "type": "image",
                "mime_type": img.mime_type,
                "data_base64": base64.b64encode(img.data).decode("ascii"),
                "filename": img.name,
            }
        )
    items.append({"type": "text", "text": prompt})
    return items


def extract_muse_media(value: Any) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, str):
            text = node.strip()
            if text.startswith("{") or text.startswith("["):
                try:
                    walk(json.loads(text))
                except json.JSONDecodeError:
                    pass
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        kind = str(node.get("kind") or node.get("type") or "").lower()
        mime = str(
            node.get("mime_type") or node.get("mimeType") or node.get("mime") or node.get("content_type") or ""
        ).lower()
        original = None
        variants = node.get("variants")
        if isinstance(variants, dict):
            original = variants.get("original")
        path = node.get("path") if isinstance(node.get("path"), str) else None
        url = original if isinstance(original, str) else (node.get("url") if isinstance(node.get("url"), str) else None)
        handle = node.get("media_handle") or node.get("mediaHandle")
        blob = f"{path or ''} {url or ''}"
        media_type = None
        if "video" in kind or mime.startswith("video/") or re.search(r"\.(mp4|webm|mov|m4v)(\?|$)", blob, re.I):
            media_type = "Video"
        elif "image" in kind or mime.startswith("image/") or re.search(r"\.(png|jpe?g|webp)(\?|$)", blob, re.I):
            media_type = "Image"
        if media_type and (path or url or handle):
            key = str(path or handle or url)
            if key not in seen:
                seen.add(key)
                found.append(
                    {
                        "type": media_type,
                        "path": path or "",
                        "url": url or "",
                        "handle": str(handle or ""),
                        "mimeType": mime or ("video/mp4" if media_type == "Video" else "image/png"),
                    }
                )
        for child in node.values():
            if isinstance(child, (dict, list, str)):
                walk(child)

    walk(value)
    return found


def collect_session_ids(value: Any, out: list[str] | None = None) -> list[str]:
    if out is None:
        out = []
    if isinstance(value, list):
        for item in value:
            collect_session_ids(item, out)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in {"session_id", "sessionId", "thread_id", "threadId"} and isinstance(item, str) and item not in out:
                out.append(item)
            collect_session_ids(item, out)
    return out


def collect_assistant_text(value: Any, out: list[str] | None = None, assistant: bool = False) -> list[str]:
    if out is None:
        out = []
    if isinstance(value, list):
        for item in value:
            collect_assistant_text(item, out, assistant)
        return out
    if not isinstance(value, dict):
        return out
    role = str(value.get("role") or value.get("author") or value.get("speaker") or "").lower()
    is_assistant = assistant or role == "assistant" or role.startswith("assistant:")
    if is_assistant:
        for key in ("text", "content", "message", "value"):
            if isinstance(value.get(key), str):
                out.append(value[key])
    for item in value.values():
        if isinstance(item, (dict, list)):
            collect_assistant_text(item, out, is_assistant)
    return out


def normalize_gateway_path(value: str) -> str:
    text = str(value or "").strip().split("?", 1)[0].split("#", 1)[0]
    if text.startswith("file://"):
        text = text[7:]
    text = text.replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    text = text.lstrip("/")
    parts = [p for p in text.split("/") if p]
    if "workspace" in parts:
        parts = parts[parts.index("workspace") :]
    elif parts and parts[0] in {"home", "Users"} and len(parts) >= 3:
        parts = parts[2:]
    return "/".join(parts)


def _cookie_header(cookies: list[dict]) -> str:
    return "; ".join(f"{c.get('name')}={c.get('value')}" for c in cookies if c.get("name") and c.get("value") is not None)


class MuseHatchClient:
    def __init__(
        self,
        cookies: list[dict] | None = None,
        *,
        request: Any | None = None,
        timeout_min: int = 12,
    ):
        """cookies = exported hub cookies; request = Playwright APIRequestContext (preferred, like Electron session.fetch)."""
        self.cookies = cookies or []
        self.request = request
        self.timeout_min = timeout_min
        self.http: httpx.AsyncClient | None = None
        self.socket = None
        self.stream = 1
        self.streams: dict[int, dict[str, Any]] = {}
        self.rx_parts: dict[Any, dict[str, Any]] = {}
        self.tx_key: bytes | None = None
        self.rx_key: bytes | None = None
        self.tx_nonce = 0
        self.rx_nonce = 0
        self.closed = False
        self.locale = "en-US"
        self._recv_task: asyncio.Task | None = None
        self._awaiting_pong = False

    async def __aenter__(self) -> MuseHatchClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _cookie(self) -> str:
        return _cookie_header(self.cookies)

    async def _http_get(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[int, str, bytes]:
        hdrs = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Origin": MUSE,
            "Referer": f"{MUSE}/",
            **(headers or {}),
        }
        if self.request is not None:
            res = await self.request.get(url, headers=hdrs, timeout=60_000)
            body = await res.body()
            return res.status, body.decode("utf-8", errors="replace"), body
        assert self.http is not None
        res = await self.http.get(url, headers=hdrs)
        return res.status_code, res.text, res.content

    async def _http_post_json(self, url: str, payload: dict[str, Any]) -> tuple[int, Any]:
        hdrs = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": MUSE,
            "Referer": f"{MUSE}/",
        }
        if self.request is not None:
            res = await self.request.post(url, headers=hdrs, data=json.dumps(payload), timeout=60_000)
            text = await res.text()
            data = None
            if text.strip():
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = None
            return res.status, data
        assert self.http is not None
        res = await self.http.post(url, headers=hdrs, json=payload)
        data = res.json() if res.content else None
        return res.status_code, data

    async def connect(self) -> None:
        cookie = self._cookie()
        if self.request is None:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Cookie": cookie,
                "Origin": MUSE,
                "Referer": f"{MUSE}/",
            }
            self.http = httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=headers)
        status, source, _raw = await self._http_get(f"{MUSE}/")
        if status >= 400:
            raise MuseHatchError("AUTH_REQUIRED", "Could not initialize Muse session.", recoverable=True)
        boot_status, boot_text, _boot_raw = await self._http_get(
            f"{MUSE}/api/hatch/bootstrap",
            headers={"Accept": "application/json"},
        )
        boot = None
        if boot_text.strip():
            try:
                boot = json.loads(boot_text)
            except json.JSONDecodeError:
                boot = None
        if boot_status == 403 and isinstance(boot, dict) and boot.get("type") == "checkpointRequired":
            checkpoint = boot.get("checkpoint_url") or ""
            raise MuseHatchError(
                "AUTH_REQUIRED",
                f"Muse Meta checkpoint required. Open Browser Hub and finish: {checkpoint}",
                recoverable=True,
            )
        html = (
            source.replace("&quot;", '"')
            .replace("&#034;", '"')
            .replace("&#34;", '"')
            .replace("&amp;", "&")
            .replace('\\"', '"')
            .replace("\\/", "/")
        )

        def get(name: str, required: bool = True) -> str | None:
            m = re.search(rf'"{name}"\s*:\s*"((?:\\.|[^"\\])*)"', html)
            if not m:
                if required:
                    raise MuseHatchError(
                        "NETWORK",
                        f"Muse bootstrap field {name} was not found. "
                        "Open Muse hub, finish login/checkpoint until the app loads.",
                        recoverable=True,
                    )
                return None
            return json.loads(f'"{m.group(1)}"')

        gateway = get("gatewayUrl") or ""
        vm = get("vmName") or ""
        admission = get("authToken") or ""
        notary = get("notaryToken", required=False)
        locale = (get("viewerLocale", required=False) or "en-US").replace("_", "-")
        vm_id = vm or (httpx.URL(gateway).host or "").split(".")[0]
        wake_status, _wake = await self._http_post_json(
            f"{MUSE}/api/hatch/vm/wake",
            {"vm_id": vm_id, "retry_count": 0, "connect_attempt_id": str(uuid.uuid4())},
        )
        if wake_status in (401, 403):
            raise MuseHatchError("AUTH_REQUIRED", "Muse session expired. Open Muse in Browser Hub again.", recoverable=True)
        if wake_status >= 400:
            raise MuseHatchError("NETWORK", f"Muse wake failed HTTP {wake_status}.", recoverable=True)
        token_status, token = await self._http_post_json(
            f"{MUSE}/api/hatch/token",
            {"vmAddress": gateway, "vmName": vm},
        )
        if token_status in (401, 403):
            raise MuseHatchError("AUTH_REQUIRED", "Muse session expired. Open Muse in Browser Hub again.", recoverable=True)
        if token_status >= 400:
            raise MuseHatchError("NETWORK", f"Muse token failed HTTP {token_status}.", recoverable=True)
        token = token if isinstance(token, dict) else {}
        params = {
            "vm_id": vm_id,
            "auth_token": token.get("token") or admission,
            "app_id": "hatch-web",
            "request_id": str(uuid.uuid4()),
        }
        notary_token = token.get("notary_token") or notary
        if notary_token:
            params["notary_token"] = notary_token
        ws_url = f"{HATCH}?{urlencode(params)}"
        import websockets

        self.socket = await websockets.connect(
            ws_url,
            additional_headers={"Cookie": cookie, "Origin": MUSE},
            max_size=16 * 1024 * 1024,
            open_timeout=15,
        )
        noise = NoiseHandshake()
        await self.socket.send(noise.message1())
        msg2 = await asyncio.wait_for(self.socket.recv(), timeout=15)
        if isinstance(msg2, str):
            msg2 = msg2.encode("latin1")
        noise.message2(msg2)
        final_msg, tx, rx = noise.message3()
        await self.socket.send(final_msg)
        self.tx_key = tx
        self.rx_key = rx
        self.locale = locale
        self._recv_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        assert self.socket is not None
        try:
            async for raw in self.socket:
                data = raw.encode("latin1") if isinstance(raw, str) else bytes(raw)
                try:
                    await self._receive(data)
                except Exception as exc:
                    self._fail_all(exc)
                    break
        except Exception as exc:
            self._fail_all(exc)

    def _encrypt(self, payload: bytes) -> bytes:
        assert self.tx_key is not None
        out = _seal(self.tx_key, _nonce12(self.tx_nonce), b"", payload)
        self.tx_nonce += 1
        return out

    def _decrypt(self, payload: bytes) -> bytes:
        assert self.rx_key is not None
        out = _open(self.rx_key, _nonce12(self.rx_nonce), b"", payload)
        self.rx_nonce += 1
        return out

    async def _receive(self, raw: bytes) -> None:
        decoded = self._decrypt(raw)
        fields = _parse_fields(decoded)
        id_f = next((f for f in fields if f[0] == 1), None)
        index_f = next((f for f in fields if f[0] == 2), None)
        total_f = next((f for f in fields if f[0] == 3), None)
        payload_f = next((f for f in fields if f[0] == 4), None)
        chunk_id = id_f[2] if id_f else 0
        index = int(index_f[2] if index_f else 0)
        total = int(total_f[2] if total_f else 1)
        chunk = payload_f[2] if payload_f else b""
        if not isinstance(chunk, (bytes, bytearray)):
            chunk = b""
        if total < 1 or total > 256 or index < 0 or index >= total or len(chunk) > MAX_FRAME:
            raise MuseHatchError("PROTOCOL", "Invalid Muse Noise frame.")
        part = self.rx_parts.get(chunk_id)
        if not part:
            part = {"total": total, "parts": {}, "size": 0}
            self.rx_parts[chunk_id] = part
        if part["total"] != total or index in part["parts"]:
            raise MuseHatchError("PROTOCOL", "Inconsistent Muse Noise frame sequence.")
        part["parts"][index] = bytes(chunk)
        part["size"] += len(chunk)
        if part["size"] > 16 * 1024 * 1024:
            raise MuseHatchError("PROTOCOL", "Muse Noise frame assembly exceeded 16 MiB.")
        if len(part["parts"]) != total:
            return
        self.rx_parts.pop(chunk_id, None)
        frame = b"".join(part["parts"][i] for i in range(total))
        service = next((f[2] for f in _parse_fields(frame) if f[0] == 1 and f[1] == 2), None)
        if not service:
            return
        sf = _parse_fields(service)
        sid_raw = next((f[2] for f in sf if f[0] == 1 and f[1] == 0), 0)
        sid = int(sid_raw)
        state = self.streams.get(sid)
        if not state:
            return
        for n, w, v in sf:
            if n == 3 and w == 2:
                fs = _parse_fields(v)
                status = int(next((x[2] for x in fs if x[0] == 1 and x[1] == 0), 0))
                body = next((x[2] for x in fs if x[0] == 3 and x[1] == 2), b"")
                end = bool(next((x[2] for x in fs if x[0] == 4 and x[1] == 0), 0))
                state["status"] = status
                if isinstance(body, (bytes, bytearray)):
                    state["chunks"].append(bytes(body))
                if end:
                    state["finish"]()
            elif n == 4 and w == 2:
                fs = _parse_fields(v)
                data = next((x[2] for x in fs if x[0] == 1 and x[1] == 2), b"")
                end = bool(next((x[2] for x in fs if x[0] == 2 and x[1] == 0), 0))
                if isinstance(data, (bytes, bytearray)):
                    state["chunks"].append(bytes(data))
                if end:
                    state["finish"]()
            elif n == 5 and w == 2:
                fs = _parse_fields(v)
                code = int(next((x[2] for x in fs if x[0] == 1 and x[1] == 0), 0))
                reason = next((x[2] for x in fs if x[0] == 2 and x[1] == 2), b"")
                reason_s = reason.decode("utf-8", errors="replace") if isinstance(reason, (bytes, bytearray)) else ""
                state["reject"](MuseHatchError("NETWORK", f"Hatch stream reset code={code}: {reason_s}"))

    def _fail_all(self, error: Exception | None = None) -> None:
        err = error or MuseHatchError("NETWORK", "Muse connection closed.")
        for state in list(self.streams.values()):
            state["reject"](err)
        self.streams.clear()

    async def request(self, method: str, path: str, params: dict | None = None, timeout_ms: int = 60_000) -> dict[str, Any]:
        assert self.socket is not None
        body = b""
        if method.upper() == "GET":
            if params:
                query = urlencode({k: str(v) for k, v in params.items()})
                path = f"{path}{'&' if '?' in path else '?'}{query}"
        else:
            body = json.dumps(params or {}).encode("utf-8")
        sid = self.stream
        self.stream += 1
        app = _app_request(method, path, body, self.locale)
        sf = _field(1, 0, sid) + _fbytes(2, app)
        frames = _split_payload(_service_envelope(sf))
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        def finish() -> None:
            self.streams.pop(sid, None)
            if not future.done():
                future.set_result({"status": state["status"], "bytes": b"".join(state["chunks"])})

        def reject(exc: Exception) -> None:
            self.streams.pop(sid, None)
            if not future.done():
                future.set_exception(exc)

        state: dict[str, Any] = {"status": 0, "chunks": [], "finish": finish, "reject": reject}
        self.streams[sid] = state
        for frame in frames:
            await self.socket.send(self._encrypt(frame))
        try:
            result = await asyncio.wait_for(future, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError as exc:
            reject(MuseHatchError("NETWORK", "Muse RPC timed out.", recoverable=True))
            raise MuseHatchError("NETWORK", "Muse RPC timed out.", recoverable=True) from exc
        status = int(result["status"])
        if status in (401, 403):
            raise MuseHatchError("AUTH_REQUIRED", "Muse session is no longer valid.", recoverable=True)
        if status == 429:
            raise MuseHatchError("RATE_LIMITED", "Muse rate limit reached.", recoverable=True)
        if status >= 500:
            raise MuseHatchError("NETWORK", f"Muse RPC returned HTTP {status}.", recoverable=True)
        if status >= 400:
            raise MuseHatchError("PROVIDER_REJECTED", f"Muse RPC returned HTTP {status}.")
        return result

    async def json_rpc(self, method: str, path: str, params: dict | None = None, timeout_ms: int = 60_000) -> Any:
        result = await self.request(method, path, params, timeout_ms)
        raw = result["bytes"]
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MuseHatchError("PROVIDER_REJECTED", "Muse RPC returned invalid JSON.") from exc

    async def subscribe(self, path: str, payload: dict, timeout_ms: int = 30_000) -> list[Any]:
        assert self.socket is not None
        sid = self.stream
        self.stream += 1
        body = json.dumps(payload).encode("utf-8")
        app = _app_request("POST", path, body, self.locale)
        sf = _field(1, 0, sid) + _fbytes(2, app)
        frames = _split_payload(_service_envelope(sf))
        loop = asyncio.get_running_loop()
        done: asyncio.Future = loop.create_future()
        events: list[Any] = []

        def finish() -> None:
            pending = b"".join(state["chunks"]).decode("utf-8", errors="replace")
            for line in pending.split("\n"):
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            self.streams.pop(sid, None)
            if not done.done():
                done.set_result(None)

        def reject(exc: Exception) -> None:
            self.streams.pop(sid, None)
            if not done.done():
                done.set_exception(exc)

        state: dict[str, Any] = {"status": 0, "chunks": [], "finish": finish, "reject": reject}
        self.streams[sid] = state
        for frame in frames:
            await self.socket.send(self._encrypt(frame))
        try:
            await asyncio.wait_for(done, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            finish()
        status = int(state["status"])
        if status in (401, 403):
            raise MuseHatchError("AUTH_REQUIRED", "Muse session is no longer valid.", recoverable=True)
        if status == 429:
            raise MuseHatchError("RATE_LIMITED", "Muse rate limit reached.", recoverable=True)
        if status >= 500:
            raise MuseHatchError("NETWORK", f"Muse chat request returned HTTP {status}.", recoverable=True)
        if status >= 400:
            raise MuseHatchError("PROVIDER_REJECTED", f"Muse chat request returned HTTP {status}.")
        return events

    async def fetch_media(self, media: dict[str, str]) -> bytes:
        from urllib.parse import quote

        attempts: list[str] = []

        async def try_download(label: str, download) -> bytes | None:
            try:
                data = await download()
                if not data:
                    raise RuntimeError("empty")
                return data
            except Exception as exc:
                attempts.append(f"{label}: {type(exc).__name__}")
                return None

        url = media.get("url") or ""
        handle = media.get("handle") or ""
        path = media.get("path") or ""
        if url and "/idea-cards/media/" in url:
            parsed = httpx.URL(url if url.startswith("http") else f"https://hatch.metaaivm.com{url}")
            params = {k: v for k, v in parsed.params.multi_items()}

            async def idea_media() -> bytes:
                return await self._rpc_bytes("GET", parsed.path, params)

            data = await try_download("idea-media URL", idea_media)
            if data:
                return data
        if handle:

            async def by_handle() -> bytes:
                return await self._rpc_bytes("GET", f"/api/idea-cards/media/{quote(handle, safe='')}", {})

            data = await try_download("media handle", by_handle)
            if data:
                return data
        if url.startswith("http://") or url.startswith("https://"):

            async def direct() -> bytes:
                status, _text, body = await self._http_get(url)
                if status >= 400:
                    raise MuseHatchError("NETWORK", f"HTTP {status}")
                return body

            data = await try_download("direct URL", direct)
            if data:
                return data
        if url.startswith("sandbox://"):
            gpath = normalize_gateway_path(url[len("sandbox://") :])
            parts = "/".join(quote(p, safe="") for p in gpath.split("/") if p)

            async def sandbox() -> bytes:
                return await self._rpc_bytes("GET", f"/fs/raw/{parts}", {})

            data = await try_download("sandbox URL", sandbox)
            if data:
                return data
        if path:
            gpath = normalize_gateway_path(path)
            parts = "/".join(quote(p, safe="") for p in gpath.split("/") if p)

            async def fs_raw() -> bytes:
                return await self._rpc_bytes("GET", f"/fs/raw/{parts}", {})

            data = await try_download("filesystem path", fs_raw)
            if data:
                return data
        raise MuseHatchError(
            "NETWORK",
            f"Unable to download generated Muse media: {'; '.join(attempts) or 'no usable media source'}",
            recoverable=True,
        )

    async def _rpc_bytes(self, method: str, path: str, params: dict) -> bytes:
        result = await self.request(method, path, params, 300_000)
        return result["bytes"]

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except Exception:
                pass
        if self.socket is not None:
            try:
                await self.socket.close()
            except Exception:
                pass
        if self.http is not None:
            await self.http.aclose()
        self._fail_all()
