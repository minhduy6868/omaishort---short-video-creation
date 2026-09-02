from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from omaishort import db
from omaishort.config import SAMPLES_DIR
from omaishort.engine.kenburns import has_audio_stream, probe_duration, probe_video_size
from omaishort.pipeline import run_job
from omaishort_schema.models import Genre, StoryInput, StoryMode


def _read_story(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


async def _run(path: Path, genre: str, language: str, seconds: int) -> str:
    db.init_db()
    text = _read_story(path)
    story = StoryInput(
        mode=StoryMode.script,
        text=text,
        target_seconds=seconds,
        genre=Genre(genre),
        language=language,
    )
    job_id = "dryrun-" + uuid.uuid4().hex[:8]
    db.create_job(job_id, story.model_dump_json())
    await run_job(job_id)
    row = db.get_job(job_id)
    assert row
    arts = db.artifacts_of(row)
    mp4 = arts.get("mp4")
    extra: dict = {}
    if mp4:
        extra["mp4"] = mp4
        extra["duration_sec"] = probe_duration(Path(str(mp4)))
        extra["size"] = probe_video_size(Path(str(mp4)))
        extra["audio"] = has_audio_stream(Path(str(mp4)))
    print(json.dumps({"id": job_id, "status": row["status"], "stage": row["stage"], "error": row["error"], **extra}, indent=2))
    if row["status"] != "done":
        raise SystemExit(1)
    return job_id


def main() -> None:
    parser = argparse.ArgumentParser(description="omaishort dry-run")
    parser.add_argument("story", nargs="?", default=str(SAMPLES_DIR / "confession-60s.md"))
    parser.add_argument("--genre", default="confession")
    parser.add_argument("--language", default="en")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()
    asyncio.run(_run(Path(args.story), args.genre, args.language, args.seconds))


if __name__ == "__main__":
    main()
