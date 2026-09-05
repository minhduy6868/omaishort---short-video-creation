from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from PIL import Image

from omaishort.config import POLLINATIONS_ENABLED, POLLINATIONS_MODEL, POLLINATIONS_URL
from omaishort.providers.placeholder import HEIGHT, WIDTH

_MIN_GAP_SEC = 16.0
_lock = asyncio.Lock()
_last_call = 0.0
_IDENTITY_PREFIX = (
    "Keep the exact same person as the reference photograph. "
    "Identical face, hair, skin, age, and clothing. "
)


def compact_image_prompt(prompt: str, limit: int = 420) -> str:
    """Keep cast, wardrobe, and location — Pollinations truncates long bible dumps."""
    insert = bool(re.search(r"(?m)^INSERT:", prompt)) or prompt.lstrip().startswith("INSERT:")
    loc = ""
    match = re.search(r"Location:\s*(.+)", prompt)
    if match:
        loc = match.group(1).strip()[:70]
    action = ""
    match = re.search(r"Action:\s*(.+)", prompt)
    if match:
        action = match.group(1).strip()[:90]
    people: list[str] = []
    ids: list[str] = []
    only_line = re.search(r"On camera ONLY:\s*([a-z0-9_, ]+)", prompt, re.I)
    if only_line:
        ids = [
            part.strip().lower()
            for part in only_line.group(1).split(",")
            if part.strip() and part.strip().lower() != "nobody"
        ]
    for raw in re.finditer(
        r"^-\s+([a-z0-9_]+):[^\n]*Appearance lock:\s*(.+?)(?:\. Clothing lock:\s*(.+?))?(?:\.|$)",
        prompt,
        flags=re.I | re.M,
    ):
        cid, appearance, clothing = raw.group(1).lower(), raw.group(2).strip(), (raw.group(3) or "").strip()
        if cid in {"location", "prop"}:
            continue
        if cid not in ids:
            ids.append(cid)
        bit = appearance[:90]
        if clothing:
            bit += f", wearing {clothing[:80]}"
        people.append(bit)
    brief = bool(re.search(r"(?m)^BRIEF:", prompt)) or prompt.lstrip().startswith("BRIEF:")
    if brief:
        parts = [
            "uninhabited 9:16 editorial still",
            "zero people",
            "zero faces",
            "zero hands",
            "no couple",
            "no presenter",
            "no crowd",
            "no on-image text",
        ]
        if action:
            parts.append(action)
        if loc:
            parts.append(loc)
    elif insert:
        parts = ["photoreal 9:16 insert", "extreme close-up", "no standing people", "no crowd", "no full-body"]
        blob = f"{action} {loc}".lower()
        if any(token in blob for token in ("phone", "lock screen", "message", "screenshot")):
            parts.append("two hands holding a smartphone, lock screen visible")
            loc = ""
        if action:
            parts.append(action)
        if loc:
            parts.append(loc)
    elif "passport still of" in prompt.lower():
        match = re.search(r"passport still of ([a-z0-9_]+)", prompt, re.I)
        who = match.group(1) if match else "person"
        app = re.search(r"Appearance lock:\s*(.+)", prompt, re.I)
        cloth = re.search(r"Clothing lock:\s*(.+)", prompt, re.I)
        parts = [f"photoreal 9:16 passport of {who}", "shoulders-up", "looking at camera", "no extra people"]
        if app:
            appearance = app.group(1).strip()[:100]
            parts.append(appearance)
            lowered_app = appearance.lower()
            if any(token in lowered_app for token in ("knot", "bun", "updo")):
                parts.append("hair tied in a low bun, not loose")
            if "stud" in lowered_app:
                parts.append("small stud earrings, not dangling")
        if cloth:
            parts.append("wearing " + cloth.group(1).strip()[:80])
        parts.append("garment fully visible on shoulders")
    else:
        only = ", ".join(ids) if ids else "the bible character"
        parts = [
            "photoreal 9:16 short-drama still",
            f"ONLY {only} in frame",
            "no extra people",
            "no crowd",
        ]
        if len(ids) == 1:
            parts.append("one person only, not a couple")
        for person in people[:2]:
            if ", wearing " in person:
                appearance, clothing = person.split(", wearing ", 1)
                parts.append(appearance[:90])
                parts.append("wearing " + clothing[:80])
            else:
                parts.append(person)
        if loc:
            parts.append(loc)
        if action:
            parts.append(action[:80])
    text = re.sub(r"\s+", " ", ", ".join(p for p in parts if p)).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0]
    if "9:16" not in text:
        text += ", photoreal 9:16"
    if "no text" not in text.lower():
        text += ", no text no watermark"
    return text


def identity_seed(prompt: str) -> int:
    lowered = prompt.lower()
    match = re.search(r"passport still of ([a-z0-9_]+)", lowered)
    if match:
        return _seed_int(f"char:{match.group(1)}")
    match = re.search(r"^id:\s*([a-z0-9_]+)", prompt, re.I | re.M)
    if match:
        return _seed_int(f"asset:{match.group(1).lower()}")
    loc = re.search(r"location:\s*[^\n]*\(([a-z0-9_]+)\)", lowered)
    only_line = re.search(r"on camera only:\s*([a-z0-9_, ]+)", lowered)
    if only_line:
        people = [
            part.strip()
            for part in only_line.group(1).split(",")
            if part.strip() not in {"nobody", ""}
        ]
    else:
        chars = re.findall(r"^-\s+([a-z0-9_]+):", prompt, re.I | re.M)
        people = [c.lower() for c in chars if c.lower() not in {"location", "prop"}]
    if loc or people:
        return _seed_int(f"scene:{loc.group(1) if loc else ''}:{'+'.join(people)}")
    action = re.search(r"action:\s*(.+)", lowered)
    return _seed_int((action.group(1)[:80] if action else prompt[:80]))


def _seed_int(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16) % 2_147_483_647


def looks_like_photo(path: Path) -> bool:
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return False
    return img.getcolors(maxcolors=256) is None


def meta_path(image_path: Path) -> Path:
    return image_path.with_suffix(".pollinations.json")


def load_ref_url(ref: Path) -> str | None:
    meta = meta_path(ref)
    if not meta.exists():
        return None
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    url = data.get("url")
    return url if isinstance(url, str) and url.startswith("http") else None


def pick_kontext_url(refs: list[Path] | None) -> str | None:
    for ref in refs or []:
        if ref.parent.name != "refs":
            continue
        url = load_ref_url(ref)
        if url:
            return url
    return None


def build_pollinations_url(
    compact: str,
    seed: int,
    *,
    image_url: str | None = None,
    model: str | None = None,
) -> str:
    base = POLLINATIONS_URL.rstrip("/")
    if image_url:
        locked = _IDENTITY_PREFIX + compact
        params = {
            "model": "kontext",
            "image": image_url,
            "width": "768",
            "height": "1344",
            "nologo": "true",
            "referrer": "omaishort",
        }
        return f"{base}/prompt/{quote(locked, safe='')}?{urlencode(params)}"
    chosen = model or POLLINATIONS_MODEL
    return (
        f"{base}/prompt/{quote(compact, safe='')}"
        f"?model={quote(chosen)}&width=768&height=1344&nologo=true"
        f"&seed={seed}&referrer=omaishort"
    )


class PollinationsImageProvider:
    name = "pollinations"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        if not POLLINATIONS_ENABLED:
            return None
        compact = compact_image_prompt(prompt)
        seed = identity_seed(prompt)
        dest.parent.mkdir(parents=True, exist_ok=True)
        image_url = pick_kontext_url(refs)
        raw: bytes | None = None
        used_url = ""
        if image_url:
            for _ in range(3):
                used_url = build_pollinations_url(compact, seed, image_url=image_url)
                raw = await _fetch_bytes(used_url)
                if raw:
                    break
        if not raw:
            models: list[str] = []
            if "passport still of" in prompt.lower() and POLLINATIONS_MODEL != "flux":
                models.append("flux")
            models.append(POLLINATIONS_MODEL)
            if POLLINATIONS_MODEL != "turbo":
                models.append("turbo")
            seen: set[str] = set()
            for model in models:
                if model in seen:
                    continue
                seen.add(model)
                used_url = build_pollinations_url(compact, seed, model=model)
                raw = await _fetch_bytes(used_url)
                if raw:
                    break
        if not raw:
            return None
        try:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            img.save(dest, "PNG")
        except Exception:
            return None
        if not looks_like_photo(dest):
            dest.unlink(missing_ok=True)
            return None
        meta_path(dest).write_text(
            json.dumps({"url": used_url, "seed": seed}, indent=2),
            encoding="utf-8",
        )
        return dest


async def _fetch_bytes(url: str) -> bytes | None:
    global _last_call
    async with _lock:
        wait = _MIN_GAP_SEC - (time.monotonic() - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
                    response = await client.get(url, headers={"Accept": "image/*"})
                _last_call = time.monotonic()
                if response.status_code in (429, 500, 502, 503):
                    print(f"pollinations {response.status_code}", flush=True)
                    await asyncio.sleep(16 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    print(f"pollinations {response.status_code}", flush=True)
                    return None
                ctype = (response.headers.get("content-type") or "").lower()
                body = response.content
                print(f"pollinations {response.status_code} {len(body)}b", flush=True)
                if "html" in ctype or body[:15].lstrip().startswith(b"<!DOCTYPE") or len(body) < 4000:
                    return None
                return body
            except Exception:
                await asyncio.sleep(2 * (attempt + 1))
        return None
