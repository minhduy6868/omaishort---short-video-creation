"""Bind user uploads onto a job dir. Paths only — no SQLite, no tokens."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from omaishort.engine.brief_media import conform_photo
from omaishort.paths import job_dir, location_refs_dir, prop_refs_dir, refs_dir
from omaishort_schema.models import AttachmentKind, CharacterBible, is_editorial


@dataclass
class AppliedAttachments:
    faces: dict[str, Path] = field(default_factory=dict)
    locations: dict[str, Path] = field(default_factory=dict)
    props: dict[str, Path] = field(default_factory=dict)
    editorial: list[Path] = field(default_factory=list)
    logo: Path | None = None
    script: Path | None = None


def _stem(filename: str) -> str:
    return Path(filename).stem.lower().replace(" ", "_")


def _match(bind: str | None, filename: str, ids: list[str]) -> str | None:
    lowered = {item.lower(): item for item in ids}
    if bind:
        key = bind.strip().lower()
        if key in lowered:
            return lowered[key]
    stem = _stem(filename)
    if stem in lowered:
        return lowered[stem]
    return None


def _copy_image(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        return conform_photo(src, dest)
    except Exception:
        shutil.copy2(src, dest)
        return dest


def apply_attachment_files(
    job_id: str,
    kind: str,
    bible: CharacterBible,
    records: list[dict],
) -> AppliedAttachments:
    """Copy owned files into the job tree. Editorial jobs ignore faces; drama ignores editorial stills."""
    applied = AppliedAttachments()
    editorial = is_editorial(kind)
    char_ids = [c.id for c in bible.characters]
    loc_ids = [loc.id for loc in bible.locations]
    prop_ids = [prop.id for prop in bible.props]
    unused_faces = [c.id for c in bible.characters if c.id.lower() != "narrator"]
    rdir = refs_dir(job_id)
    loc_dir = location_refs_dir(job_id)
    prop_dir = prop_refs_dir(job_id)
    work = job_dir(job_id) / "attachments"
    work.mkdir(parents=True, exist_ok=True)

    for rec in records:
        src = Path(str(rec["path"]))
        if not src.is_file():
            continue
        akind = rec.get("kind")
        bind = rec.get("bind")
        filename = str(rec.get("filename") or src.name)
        if akind == AttachmentKind.script.value:
            dest = job_dir(job_id) / "input_attachment.txt"
            dest.write_bytes(src.read_bytes())
            applied.script = dest
            continue
        if akind == AttachmentKind.logo.value:
            dest = work / f"logo{src.suffix.lower() or '.png'}"
            shutil.copy2(src, dest)
            applied.logo = dest
            continue
        if akind == AttachmentKind.editorial.value:
            if editorial:
                dest = work / f"editorial_{len(applied.editorial):02d}.png"
                applied.editorial.append(_copy_image(src, dest))
            continue
        if editorial:
            continue
        if akind == AttachmentKind.face.value:
            cid = _match(bind, filename, char_ids)
            if not cid and unused_faces:
                cid = unused_faces.pop(0)
            elif cid and cid in unused_faces:
                unused_faces.remove(cid)
            if not cid:
                continue
            dest = rdir / f"{cid}.png"
            applied.faces[cid] = _copy_image(src, dest)
        elif akind == AttachmentKind.location.value:
            lid = _match(bind, filename, loc_ids)
            if lid:
                dest = loc_dir / f"{lid}.png"
                applied.locations[lid] = _copy_image(src, dest)
        elif akind == AttachmentKind.prop.value:
            pid = _match(bind, filename, prop_ids)
            if pid:
                dest = prop_dir / f"{pid}.png"
                applied.props[pid] = _copy_image(src, dest)
    return applied
