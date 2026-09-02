from __future__ import annotations

import hashlib
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

WIDTH = 1080
HEIGHT = 1920

LOCATION_PALETTES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    "kitchen": ((42, 22, 14), (12, 8, 6), (232, 168, 72)),
    "hallway": ((28, 22, 18), (8, 6, 5), (210, 150, 80)),
    "bedroom": ((24, 16, 28), (8, 6, 10), (180, 110, 90)),
    "bathroom": ((18, 22, 24), (6, 8, 9), (160, 190, 200)),
    "living_room": ((22, 18, 16), (8, 7, 6), (200, 140, 70)),
    "street": ((10, 14, 28), (4, 6, 10), (240, 170, 60)),
    "door": ((20, 16, 14), (6, 5, 4), (190, 120, 50)),
}


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


def _seed(prompt: str) -> int:
    return int(hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8], 16)


def _parse_hint(prompt: str) -> dict:
    lowered = prompt.lower()
    location_id = "interior"
    for key in LOCATION_PALETTES:
        if key.replace("_", " ") in lowered or f"({key})" in lowered or f" {key}" in lowered:
            location_id = key
            break
    camera = "medium"
    if "close_up" in lowered or "close-up" in lowered:
        camera = "close_up"
    elif "wide" in lowered:
        camera = "wide"
    chars: list[tuple[str, str]] = []
    for match in re.finditer(r"^-\s+([a-z0-9_]+):\s+(\d+)?\s*(female|male|person)?", prompt, re.I | re.M):
        chars.append((match.group(1).lower(), (match.group(3) or "person").lower()))
    if not chars:
        n = lowered.count("female") + lowered.count("male") + lowered.count("wife") + lowered.count("husband")
        for i in range(max(1, min(3, n or 1))):
            chars.append((f"p{i}", "female" if i == 0 else "male"))
    kind = "scene"
    if "passport still of a location" in lowered or "empty of people" in lowered:
        kind = "location"
    elif "portrait / passport" in lowered or "shoulders-up" in lowered:
        kind = "portrait"
    elif "prop passport" in lowered or "isolated object" in lowered:
        kind = "prop"
    elif "insert / phone" in lowered or "phone screen close" in lowered or "lock screen" in lowered:
        kind = "insert"
    return {"location_id": location_id, "camera": camera, "chars": chars[:3], "kind": kind}


def _gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    strip = Image.new("RGB", (2, HEIGHT), top)
    pix = strip.load()
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        pix[0, y] = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        pix[1, y] = pix[0, y]
    return strip.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)


def _vignette(img: Image.Image, strength: float = 0.55) -> Image.Image:
    overlay = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(overlay)
    inset = int(80 + 40 * strength)
    draw.ellipse((-inset, -40, WIDTH + inset, HEIGHT + 80), fill=255)
    overlay = overlay.filter(ImageFilter.GaussianBlur(90))
    return Image.composite(img, Image.new("RGB", img.size, (0, 0, 0)), overlay)


def _blob(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    draw.ellipse(xy, fill=color)


def _draw_set(draw: ImageDraw.ImageDraw, location_id: str, accent: tuple[int, int, int]) -> None:
    floor_y = 1180
    draw.polygon([(0, floor_y), (WIDTH, floor_y), (WIDTH, HEIGHT), (0, HEIGHT)], fill=(10, 8, 7))
    if location_id == "kitchen":
        draw.rectangle((0, 420, WIDTH, 980), fill=(38, 24, 16))
        for x in (80, 280, 480, 680, 880):
            draw.rectangle((x, 460, x + 160, 900), fill=(52, 32, 20), outline=(70, 44, 28), width=3)
        draw.rectangle((0, 900, WIDTH, 940), fill=accent)
        draw.rectangle((720, 520, 1020, 820), fill=(18, 28, 40))
    elif location_id == "hallway":
        draw.polygon([(380, 360), (700, 360), (920, floor_y), (160, floor_y)], fill=(32, 26, 22))
        _blob(draw, (200, 480, 280, 620), accent)
        _blob(draw, (800, 480, 880, 620), accent)
    elif location_id == "bedroom":
        draw.rounded_rectangle((120, 980, 960, 1420), radius=24, fill=(48, 32, 44))
        _blob(draw, (820, 520, 980, 760), accent)
    elif location_id == "bathroom":
        draw.rounded_rectangle((280, 420, 800, 900), radius=180, fill=(60, 70, 74), outline=accent, width=8)
        draw.rectangle((200, 900, 880, 1100), fill=(40, 44, 46))
    elif location_id == "living_room":
        draw.rounded_rectangle((80, 1020, 1000, 1380), radius=30, fill=(36, 28, 24))
        _blob(draw, (140, 560, 280, 820), accent)
    elif location_id == "street":
        draw.rectangle((0, 900, WIDTH, HEIGHT), fill=(8, 10, 14))
        for x in (180, 540, 900):
            draw.rectangle((x, 200, x + 18, 900), fill=(30, 32, 40))
            _blob(draw, (x - 40, 160, x + 70, 280), accent)
    elif location_id == "door":
        draw.rounded_rectangle((280, 360, 800, 1500), radius=12, fill=(48, 32, 22), outline=(90, 60, 36), width=8)
        _blob(draw, (620, 880, 700, 960), (180, 160, 120))
    else:
        draw.rectangle((80, 700, 1000, 1100), fill=(30, 24, 20))


def _figure(
    draw: ImageDraw.ImageDraw,
    cx: int,
    baseline: int,
    scale: float,
    *,
    female: bool,
    hue: int,
) -> None:
    skin = _hsl_to_rgb(28, 0.38, 0.62)
    hair = _hsl_to_rgb(hue, 0.35, 0.12)
    cloth = _hsl_to_rgb((hue + 28) % 360, 0.28, 0.22)
    head_r = int(52 * scale)
    head_y = baseline - int(340 * scale)
    shoulder_w = int((70 if female else 92) * scale)
    torso_h = int(220 * scale)
    draw.rounded_rectangle(
        (cx - shoulder_w, head_y + head_r - 10, cx + shoulder_w, head_y + head_r + torso_h),
        radius=int(36 * scale),
        fill=cloth,
    )
    draw.ellipse((cx - head_r, head_y - head_r, cx + head_r, head_y + head_r), fill=skin)
    if female:
        draw.ellipse((cx + int(18 * scale), head_y - int(head_r * 1.35), cx + int(48 * scale), head_y - int(head_r * 0.2)), fill=hair)
        draw.pieslice((cx - head_r - 4, head_y - head_r - 8, cx + head_r + 4, head_y + 8), 180, 360, fill=hair)
    else:
        draw.pieslice((cx - head_r - 2, head_y - head_r - 2, cx + head_r + 2, head_y + 6), 200, 340, fill=hair)


def _draw_phone(draw: ImageDraw.ImageDraw) -> None:
    draw.rounded_rectangle((330, 520, 750, 1280), radius=48, fill=(12, 12, 14), outline=(80, 80, 88), width=8)
    draw.rounded_rectangle((360, 580, 720, 1180), radius=12, fill=(40, 28, 22))
    _blob(draw, (470, 700, 610, 860), (210, 170, 130))


def paint_placeholder_still(prompt: str, refs: list[Path] | None = None) -> Image.Image:
    hint = _parse_hint(prompt)
    seed = _seed(prompt)
    top, bottom, accent = LOCATION_PALETTES.get(hint["location_id"], LOCATION_PALETTES["kitchen"])
    if hint["kind"] == "portrait":
        top, bottom = _hsl_to_rgb(seed % 360, 0.12, 0.22), (18, 14, 12)
    img = _gradient(top, bottom)
    draw = ImageDraw.Draw(img)
    if hint["kind"] == "location":
        _draw_set(draw, hint["location_id"], accent)
    elif hint["kind"] == "prop" or hint["kind"] == "insert":
        _draw_set(draw, hint["location_id"], accent)
        _draw_phone(draw)
    elif hint["kind"] == "portrait":
        female = "female" in prompt.lower() or "wife" in prompt.lower()
        _figure(draw, WIDTH // 2, 1500, 2.15, female=female, hue=seed % 360)
    else:
        _draw_set(draw, hint["location_id"], accent)
        scale = {"close_up": 1.55, "wide": 0.85}.get(hint["camera"], 1.12)
        n = max(1, len(hint["chars"]))
        span = 420 if n > 1 else 0
        start = WIDTH // 2 - span // 2
        for i, (_cid, gender) in enumerate(hint["chars"]):
            cx = start + (span * i // max(1, n - 1) if n > 1 else 0)
            _figure(draw, cx, 1480, scale, female=gender != "male", hue=(seed + i * 40) % 360)
    img = _vignette(img)
    if refs:
        _stamp_refs(img, refs)
    return img


def _stamp_refs(img: Image.Image, refs: list[Path]) -> None:
    x = 48
    for path in refs[:3]:
        try:
            face = Image.open(path).convert("RGB")
        except Exception:
            continue
        face = face.resize((160, 160), Image.Resampling.LANCZOS)
        mask = Image.new("L", (160, 160), 0)
        ImageDraw.Draw(mask).ellipse((4, 4, 156, 156), fill=255)
        img.paste(face, (x, HEIGHT - 220), mask)
        x += 176
