from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from omaishort import db
from omaishort.config import SAMPLES_DIR
from omaishort.engine.brief_media import (
    fetch_article,
    fetch_github_project,
    looks_like_github,
    looks_like_url,
    prefer_readme_language,
)
from omaishort.engine.kenburns import has_audio_stream, probe_duration, probe_video_size
from omaishort.pipeline import run_job
from omaishort_schema.models import Genre, MixSettings, StoryInput, StoryMode, VideoKind, is_editorial


def _read_story(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _genre_for(kind: VideoKind, genre: str) -> Genre:
    chosen = Genre(genre)
    if is_editorial(kind) and chosen not in {Genre.news, Genre.knowledge}:
        return Genre.knowledge if kind == VideoKind.knowledge else Genre.news
    return chosen


async def _run(
    story_arg: str,
    genre: str,
    language: str,
    seconds: int,
    kind: str,
    source_url: str | None,
    logo: bool = False,
) -> str:
    db.init_db()
    url = (source_url or "").strip() or None
    text = ""
    if looks_like_url(story_arg):
        url = story_arg.strip()
        if looks_like_github(url):
            kind = "knowledge"
            page = await fetch_github_project(url)
        else:
            page = await fetch_article(url)
            if kind == "drama":
                kind = "news"
        text = page.text
        if looks_like_github(url) and not str(language).lower().startswith("vi"):
            language = prefer_readme_language(text, language)
        elif language == "en" and any(host in url for host in ("vnexpress", "tuoitre", "thanhnien", "dantri", "vietnamnet")):
            language = "vi"
    else:
        path = Path(story_arg)
        text = _read_story(path) if path.is_file() else story_arg.strip()
    if url and len(text) < 8:
        page = await fetch_github_project(url) if looks_like_github(url) else await fetch_article(url)
        text = page.text
    kind_enum = VideoKind(kind)
    story = StoryInput(
        mode=StoryMode.script,
        kind=kind_enum,
        text=text,
        target_seconds=seconds,
        genre=_genre_for(kind_enum, genre),
        language=language,
        source_url=url,
        mix=MixSettings(logo_enabled=logo),
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
    extra["source_url"] = url or arts.get("source_url")
    print(json.dumps({"id": job_id, "status": row["status"], "stage": row["stage"], "error": row["error"], **extra}, indent=2))
    if row["status"] != "done":
        raise SystemExit(1)
    return job_id


def main() -> None:
    parser = argparse.ArgumentParser(description="omaishort dry-run")
    parser.add_argument("story", nargs="?", default=str(SAMPLES_DIR / "confession-60s.md"))
    parser.add_argument("--kind", default="drama", choices=["drama", "news", "knowledge", "brief"])
    parser.add_argument("--genre", default="confession")
    parser.add_argument("--language", default="en")
    parser.add_argument("--seconds", type=int, default=0, help="Target length. 0 = 90s for news/knowledge, 60s for drama")
    parser.add_argument("--source-url", default="", help="News article or GitHub repo URL")
    parser.add_argument("--logo", action="store_true", help="Overlay assets/logo on the MP4")
    parser.add_argument("--chatgpt-login", action="store_true", help="Open Chrome once to save a ChatGPT session")
    args = parser.parse_args()
    if args.chatgpt_login:
        from omaishort.providers.chatgpt_web import login

        raise SystemExit(0 if asyncio.run(login()) else 1)
    kind = args.kind
    if looks_like_url(args.story) and kind == "drama":
        kind = "knowledge" if looks_like_github(args.story) else "news"
    seconds = args.seconds if args.seconds else (90 if kind in {"news", "knowledge", "brief"} else 60)
    asyncio.run(_run(args.story, args.genre, args.language, seconds, kind, args.source_url or None, logo=args.logo))


if __name__ == "__main__":
    main()
