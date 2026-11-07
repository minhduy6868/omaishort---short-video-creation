from __future__ import annotations

import asyncio
import contextlib
import json
import traceback
from pathlib import Path

from omaishort import config, db
from omaishort.config import WHISPER_MODEL, default_mix_settings, default_subtitle_style
from omaishort.engine.apply_attachments import apply_attachment_files
from omaishort.engine.analyzer import analyze_story, write_knowledge_script
from omaishort.engine.brief_media import (
    assign_editorial_stills,
    conform_photo,
    fetch_article,
    fetch_github_project,
    fetch_knowledge_topic,
    looks_like_github,
    looks_like_url,
    prefer_readme_language,
)
from omaishort.engine.fallback import clamp_brief_storyboard, fallback_analyze, fallback_plan
from omaishort.engine.captions import resolve_word_stamps, words_to_ass
from omaishort.engine.compose import compose_short
from omaishort.engine.image_prompts import (
    build_location_prompt,
    build_prop_prompt,
    build_ref_prompt,
    build_scene_prompt,
    fill_image_prompts,
    scene_still_refs,
)
from omaishort.engine.planner import plan_scenes
from omaishort.engine.rescale import rescale_to_audio
from omaishort.engine.timeline import build_timeline
from omaishort.paths import audio_dir, job_dir, location_refs_dir, prop_refs_dir, refs_dir, render_dir, stills_dir
from omaishort.providers.image import generate_image
from omaishort.providers.smart_image_search import resolve_scene_still
from omaishort.providers.tts import join_scene_narration, silence_audio, synthesize_speech
from omaishort.engine.kenburns import has_audio_stream, probe_duration, probe_video_size
from omaishort_schema.models import Genre, JobStage, JobStatus, MixSettings, StoryInput, VideoKind, is_editorial
from omaishort.uploads import disk_path


def _is_paused(job_id: str) -> bool:
    row = db.get_job(job_id)
    return bool(row and row.get("status") == JobStatus.paused.value)


def _remote_search_enabled() -> bool:
    return bool(
        config.POLLINATIONS_ENABLED
        or config.GROK_WEB_ENABLED
        or config.CHATGPT_WEB_ENABLED
        or config.XAI_API_KEY
        or config.OPENAI_API_KEY
        or config.GEMINI_API_KEY
    )


def _attachment_records(story: StoryInput, user_id: str | None) -> list[dict]:
    if not user_id or not story.attachments:
        return []
    rows: list[dict] = []
    for link in story.attachments:
        rec = db.get_attachment(link.id)
        if not rec or rec["user_id"] != user_id:
            continue
        path = disk_path(rec)
        if not path.is_file():
            continue
        rows.append(
            {
                "kind": rec["kind"],
                "bind": link.bind,
                "filename": rec["filename"],
                "path": path,
            }
        )
    return rows


async def _speak_voiceover(job_id: str, story: StoryInput, vo: str):
    """TTS can run while stills are fetched. A miss becomes silence, same as before."""
    voice_path = audio_dir(job_id) / "voiceover.mp3"
    try:
        tts = await synthesize_speech(vo, voice_path, story.language, story.voice_id)
        return tts.path, tts.provider, tts.words
    except Exception:
        seconds = max(story.target_seconds, len(vo.split()) / 2.5)
        path = await silence_audio(audio_dir(job_id) / "voiceover.mp3", seconds)
        return path, "silence", None


def _dump(job_id: str, name: str, payload) -> Path:
    path = job_dir(job_id) / name
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    db.dump_json(path, data)
    return path


async def run_job(job_id: str) -> None:
    row = db.get_job(job_id)
    if not row:
        return
    story = StoryInput.model_validate_json(row["input_json"])
    artifacts: dict[str, str] = {}
    providers: dict[str, str] = {}
    article_urls: list[str] | None = None
    article_captions: dict[str, str] = {}
    speak_task: asyncio.Task | None = None
    writes_open = True
    write_lock = asyncio.Lock()
    try:
        if not story.source_url and looks_like_url(story.text.strip()):
            story = story.model_copy(update={"source_url": story.text.strip()})
        if is_editorial(story.kind) and story.source_url:
            try:
                if looks_like_github(story.source_url):
                    page = await fetch_github_project(story.source_url)
                    lang = story.language
                    if not str(lang).lower().startswith("vi"):
                        lang = prefer_readme_language(page.text, lang)
                    extract = page.text if len(page.text) >= 8 else story.text
                    script, script_src, script_note = await write_knowledge_script(
                        page.title or story.source_url,
                        extract,
                        lang,
                        story.target_seconds,
                        topic=f"thuyết minh {story.source_url}",
                        script_brief=story.script_brief or "",
                    )
                    if script_src == "wiki":
                        from omaishort.engine.brief_media import knowledge_spoken_from_notes

                        script, script_src = knowledge_spoken_from_notes(
                            extract, name=page.title or "skills"
                        ), "github"
                    _dump(
                        job_id,
                        "script.json",
                        {
                            "text": script,
                            "provider": script_src,
                            "note": script_note,
                            "source": story.source_url,
                            "script_brief": story.script_brief,
                        },
                    )
                    artifacts["script_provider"] = script_src
                    if script_note:
                        artifacts["script_note"] = script_note
                    providers["script"] = script_src
                    story = story.model_copy(
                        update={
                            "kind": VideoKind.knowledge,
                            "genre": Genre.knowledge,
                            "text": script,
                            "language": lang,
                        }
                    )
                else:
                    page = await fetch_article(story.source_url)
                    extract = page.text if page.text and len(page.text) >= 8 else story.text
                    script, script_src, script_note = await write_knowledge_script(
                        page.title or story.source_url,
                        extract,
                        story.language,
                        story.target_seconds,
                        topic=page.title or story.text[:80],
                        script_brief=story.script_brief or "",
                        prompt_name="news_script.txt",
                    )
                    if script and len(script) >= 8:
                        story = story.model_copy(update={"text": script})
                    script_path = _dump(
                        job_id,
                        "script.json",
                        {
                            "title": page.title or story.source_url,
                            "provider": script_src,
                            "note": script_note,
                            "text": story.text,
                            "source": story.source_url,
                            "script_brief": story.script_brief,
                        },
                    )
                    artifacts["script"] = script_path.as_posix()
                    artifacts["script_provider"] = script_src
                    if script_note:
                        artifacts["script_note"] = script_note
                    providers["script"] = script_src
                article_urls = page.image_urls
                article_captions = page.image_captions
                artifacts["source_url"] = story.source_url
                providers["article"] = f"{len(article_urls)} photos"
            except Exception as exc:
                providers["article"] = f"fetch_failed:{type(exc).__name__}"
        elif story.kind == VideoKind.knowledge and not (story.source_url or "").strip():
            topic = story.text
            try:
                page = await fetch_knowledge_topic(topic, story.language)
                article_urls = page.image_urls
                article_captions = page.image_captions
                if page.url:
                    artifacts["source_url"] = page.url
                providers["article"] = f"topic:{page.title}:{len(article_urls)} photos"
            except Exception as exc:
                page = None
                providers["article"] = f"topic_failed:{type(exc).__name__}"
            if _is_paused(job_id):
                return
            db.update_job(job_id, status=JobStatus.running.value, progress="script")
            title = (page.title if page else "") or topic
            extract = (page.text if page else "") or ""
            script, script_src, script_note = await write_knowledge_script(
                title,
                extract,
                story.language,
                story.target_seconds,
                topic=topic,
                script_brief=story.script_brief or "",
            )
            if _is_paused(job_id):
                return
            providers["script"] = script_src
            story = story.model_copy(
                update={
                    "text": script if len(script) >= 8 else topic,
                    "source_url": (page.url if page else None) or story.source_url,
                }
            )
            script_path = _dump(
                job_id,
                "script.json",
                {
                    "title": title,
                    "provider": script_src,
                    "note": script_note,
                    "text": story.text,
                    "script_brief": story.script_brief,
                },
            )
            artifacts["script"] = script_path.as_posix()
            artifacts["script_provider"] = script_src
            if script_note:
                artifacts["script_note"] = script_note
            db.update_job(job_id, artifacts_json=json.dumps(artifacts), progress="script")
        if _is_paused(job_id):
            return
        db.update_job(job_id, status=JobStatus.running.value, stage=JobStage.analyze.value, progress="analyze")
        if providers.get("script") in {"llm", "chatgpt-web"}:
            bible, structure = fallback_analyze(story)
            src = "script"
        else:
            bible, structure, src = await analyze_story(story)
        if _is_paused(job_id):
            return
        providers["analyzer"] = src
        _dump(job_id, "bible.json", bible)
        _dump(job_id, "structure.json", structure)
        db.update_job(
            job_id,
            bible_json=bible.model_dump_json(),
            structure_json=structure.model_dump_json(),
            stage=JobStage.plan.value,
            progress="plan",
        )

        if providers.get("script") in {"llm", "chatgpt-web"}:
            board = fallback_plan(story, bible, structure)
            fill_image_prompts(board, bible)
            plan_src = "script"
        else:
            board, plan_src = await plan_scenes(story, bible, structure)
        if _is_paused(job_id):
            return
        providers["planner"] = plan_src
        if is_editorial(story.kind):
            clamp_brief_storyboard(board, story.target_seconds, story.language)
        _dump(job_id, "storyboard.json", board)
        db.update_job(job_id, storyboard_json=board.model_dump_json(), stage=JobStage.refs.value, progress="refs")
        vo = join_scene_narration([scene.dialogue_or_vo for scene in board.scenes])
        speak_task = asyncio.create_task(_speak_voiceover(job_id, story, vo))

        applied = apply_attachment_files(
            job_id,
            story.kind.value,
            bible,
            _attachment_records(story, row.get("user_id")),
        )
        if applied.logo:
            mix = (story.mix or MixSettings()).model_copy(
                update={"logo_enabled": True, "logo_path": applied.logo.as_posix()}
            )
            story = story.model_copy(update={"mix": mix})
        if applied.script:
            artifacts["input_attachment"] = applied.script.as_posix()

        rdir = refs_dir(job_id)
        loc_dir = location_refs_dir(job_id)
        prop_dir = prop_refs_dir(job_id)
        image_slots = asyncio.Semaphore(2)
        if not is_editorial(story.kind):

            async def _one_passport(char) -> None:
                dest = rdir / f"{char.id}.png"
                if char.id in applied.faces and dest.exists():
                    char.reference_image = dest.as_posix()
                    async with write_lock:
                        if not writes_open:
                            return
                        artifacts[f"ref_{char.id}"] = dest.as_posix()
                        providers[f"ref_{char.id}"] = "attachment"
                    return
                prompt = build_ref_prompt(char)
                async with image_slots:
                    path, pname = await generate_image(prompt, dest, photo=True)
                char.reference_image = path.as_posix()
                async with write_lock:
                    if not writes_open:
                        return
                    providers[f"ref_{char.id}"] = pname
                    artifacts[f"ref_{char.id}"] = path.as_posix()

            await asyncio.gather(*[_one_passport(char) for char in bible.characters])
            for loc in bible.locations:
                dest = loc_dir / f"{loc.id}.png"
                if loc.id in applied.locations and dest.exists():
                    loc.reference_image = dest.as_posix()
                    artifacts[f"loc_{loc.id}"] = dest.as_posix()
                    providers[f"loc_{loc.id}"] = "attachment"
                    continue
                prompt = build_location_prompt(loc)
                path, pname = await generate_image(prompt, dest, skip_remote=True)
                providers[f"loc_{loc.id}"] = pname
                loc.reference_image = path.as_posix()
                artifacts[f"loc_{loc.id}"] = path.as_posix()
            for prop in bible.props:
                dest = prop_dir / f"{prop.id}.png"
                if prop.id in applied.props and dest.exists():
                    prop.reference_image = dest.as_posix()
                    artifacts[f"prop_{prop.id}"] = dest.as_posix()
                    providers[f"prop_{prop.id}"] = "attachment"
                    continue
                prompt = build_prop_prompt(prop)
                path, pname = await generate_image(prompt, dest, skip_remote=True)
                providers[f"prop_{prop.id}"] = pname
                prop.reference_image = path.as_posix()
                artifacts[f"prop_{prop.id}"] = path.as_posix()
        else:
            providers["refs"] = "skipped_brief"
        if _is_paused(job_id):
            if speak_task is not None and not speak_task.done():
                speak_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await speak_task
            return
        fill_image_prompts(board, bible)
        _dump(job_id, "bible.json", bible)
        _dump(job_id, "storyboard.json", board)

        db.update_job(
            job_id,
            stage=JobStage.stills.value,
            progress="stills",
            bible_json=bible.model_dump_json(),
            artifacts_json=json.dumps(artifacts),
        )
        sdir = stills_dir(job_id)
        stills: dict[str, Path] = {}
        sourced_by_id: dict[str, Path] = {}
        source_kind = "generated"
        if is_editorial(story.kind):
            if not _is_paused(job_id):
                db.update_job(job_id, progress="stills:search")
            sourced_by_id, source_kind = await assign_editorial_stills(
                scenes=board.scenes,
                source_url=story.source_url,
                article_urls=article_urls,
                captions=article_captions,
                dest_dir=sdir / "sourced",
                title=board.title or story.text[:80],
                local_paths=applied.editorial,
            )
            providers["brief_stills"] = source_kind
        total_stills = max(1, len(board.scenes))
        done_stills = 0

        async def _one_still(scene) -> None:
            nonlocal done_stills
            dest = sdir / f"{scene.still_id}.png"
            src = sourced_by_id.get(scene.still_id)
            if src:
                conform_photo(src, dest)
                path, pname = dest, source_kind
            elif is_editorial(story.kind):
                async with image_slots:
                    path, pname = await resolve_scene_still(
                        prompt=scene.image_prompt or scene.action,
                        vo=scene.dialogue_or_vo,
                        title=board.title or story.text[:80],
                        dest=dest,
                        source="auto",
                        editorial=True,
                        skip_remote=not _remote_search_enabled(),
                    )
            else:
                refs = scene_still_refs(
                    scene, refs_dir=rdir, location_dir=loc_dir, prop_dir=prop_dir
                )
                async with image_slots:
                    path, pname = await generate_image(scene.image_prompt, dest, refs, photo=True)
            async with write_lock:
                if not writes_open:
                    return
                providers[f"still_{scene.still_id}"] = pname
                stills[scene.still_id] = path
                artifacts[scene.still_id] = path.as_posix()
                done_stills += 1
                if not _is_paused(job_id):
                    db.update_job(
                        job_id,
                        artifacts_json=json.dumps(artifacts),
                        progress=f"stills:{done_stills}/{total_stills}",
                    )

        await asyncio.gather(*[_one_still(scene) for scene in board.scenes])

        pause_requested = _is_paused(job_id) or bool((story.mix or MixSettings()).pause_before_render)
        if pause_requested:
            if speak_task is not None and not speak_task.done():
                speak_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await speak_task
            artifacts["providers"] = json.dumps(providers)
            db.update_job(
                job_id,
                status=JobStatus.paused.value,
                stage=JobStage.stills.value,
                progress="paused:review",
                artifacts_json=json.dumps(artifacts),
            )
            return

        if speak_task is not None and not speak_task.done():
            db.update_job(job_id, stage=JobStage.tts.value, progress="tts")
        voice_path, tts_name, edge_words = await speak_task
        if _is_paused(job_id):
            return
        providers["tts"] = tts_name
        duration = probe_duration(voice_path) or float(story.target_seconds)
        board = rescale_to_audio(board, duration)
        _dump(job_id, "storyboard.json", board)
        artifacts["voiceover"] = voice_path.as_posix()

        db.update_job(job_id, stage=JobStage.captions.value, progress="captions", storyboard_json=board.model_dump_json())
        stamps, cap_src = resolve_word_stamps(
            edge_words=edge_words,
            audio_path=voice_path,
            script=vo,
            duration=duration,
            whisper_model=WHISPER_MODEL,
        )
        if _is_paused(job_id):
            return
        providers["captions"] = cap_src
        ass_path = render_dir(job_id) / "captions.ass"
        style = story.subtitle or default_subtitle_style()
        words_to_ass(stamps, ass_path, style=style)
        artifacts["captions"] = ass_path.as_posix()

        db.update_job(job_id, stage=JobStage.render.value, progress="render")
        mp4 = render_dir(job_id) / "short.mp4"
        mix = story.mix or default_mix_settings()
        await compose_short(board, stills, voice_path, ass_path, mp4, render_dir(job_id), mix=mix)
        if _is_paused(job_id):
            return
        _dump(job_id, "storyboard.json", board)
        motion_path = render_dir(job_id) / "motion.json"
        i2v_ids: set[str] = set()
        if motion_path.exists():
            motion = json.loads(motion_path.read_text(encoding="utf-8"))
            i2v_ids = set(motion.get("i2v_still_ids") or [])
            artifacts["motion"] = motion_path.as_posix()
            artifacts["motion_mode"] = str(motion.get("mode") or "kenburns")
        timeline = build_timeline(board, stills, voice_path, duration, i2v_still_ids=i2v_ids)
        timeline_path = _dump(job_id, "timeline.json", timeline)
        size = probe_video_size(mp4)
        if size != (1080, 1920):
            raise RuntimeError(f"mp4 is {size}, expected 1080x1920")
        if not has_audio_stream(mp4):
            raise RuntimeError("mp4 has no audio")
        artifacts["mp4"] = mp4.as_posix()
        artifacts["timeline"] = timeline_path.as_posix()
        artifacts["providers"] = json.dumps(providers)

        from omaishort.storage import inspect_job_storage

        storage_info = inspect_job_storage(job_id, row)
        storage_info["duration_sec"] = round(float(duration), 2)
        storage_info["width"] = size[0]
        storage_info["height"] = size[1]

        db.update_job(
            job_id,
            status=JobStatus.done.value,
            stage=JobStage.done.value,
            progress="done",
            timeline_json=timeline.model_dump_json(),
            artifacts_json=json.dumps(artifacts),
            storage_json=json.dumps(storage_info),
            error=None,
        )
    except Exception as exc:
        writes_open = False
        async with write_lock:
            pass
        if speak_task is not None and not speak_task.done():
            speak_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await speak_task
        db.update_job(
            job_id,
            status=JobStatus.failed.value,
            progress="failed",
            error=f"{exc}\n{traceback.format_exc()[-2000:]}",
        )
        raise


async def regenerate_scene_still(
    job_id: str,
    scene_index: int,
    custom_prompt: str | None = None,
    *,
    source: str = "auto",
) -> dict[str, object]:
    """Regenerate or refetch a single scene's still image (via 'auto', 'grok', 'chatgpt', or 'search')."""
    from omaishort_schema.models import CharacterBible, Storyboard

    row = db.get_job(job_id)
    if not row or not row.get("storyboard_json"):
        raise ValueError("storyboard not ready")
    story = StoryInput.model_validate_json(row["input_json"])
    bible = (
        CharacterBible.model_validate_json(row["bible_json"])
        if row.get("bible_json")
        else fallback_analyze(story)[0]
    )
    board = Storyboard.model_validate_json(row["storyboard_json"])
    target = next((s for s in board.scenes if s.index == scene_index), None)
    if target is None and 1 <= scene_index <= len(board.scenes):
        target = board.scenes[scene_index - 1]
    if target is None:
        raise ValueError(f"scene {scene_index} not found")

    if custom_prompt and custom_prompt.strip():
        target.action = custom_prompt.strip()
        target.image_prompt = custom_prompt.strip()
    elif not (target.image_prompt or "").strip():
        target.image_prompt = build_scene_prompt(target, bible)

    sdir = stills_dir(job_id)
    sdir.mkdir(parents=True, exist_ok=True)
    safe_still_id = Path(target.still_id).name
    dest = sdir / f"{safe_still_id}.png"
    rdir = refs_dir(job_id)
    loc_dir = location_refs_dir(job_id)
    prop_dir = prop_refs_dir(job_id)

    refs = (
        []
        if is_editorial(board.kind)
        else scene_still_refs(target, refs_dir=rdir, location_dir=loc_dir, prop_dir=prop_dir)
    )
    src_mode = (source or "auto").strip().lower()
    pname = "generated"
    if src_mode in {"grok", "chatgpt", "search"}:
        _path, pname = await resolve_scene_still(
            prompt=custom_prompt.strip() if (custom_prompt and custom_prompt.strip()) else (target.image_prompt or target.action),
            vo=target.dialogue_or_vo,
            title=board.title or story.text[:80],
            dest=dest,
            source=src_mode,
            refs=refs,
            editorial=is_editorial(board.kind),
            skip_remote=not _remote_search_enabled(),
        )
    elif is_editorial(board.kind) and not (custom_prompt and custom_prompt.strip()):
        sourced, skind = await assign_editorial_stills(
            scenes=[target],
            source_url=story.source_url,
            article_urls=None,
            captions={},
            dest_dir=sdir / "sourced",
            title=board.title or story.text[:80],
            local_paths=[],
        )
        src_path = sourced.get(target.still_id)
        if src_path and src_path.is_file():
            conform_photo(src_path, dest)
            pname = skind
        else:
            _path, pname = await resolve_scene_still(
                prompt=target.image_prompt or target.action,
                vo=target.dialogue_or_vo,
                title=board.title or story.text[:80],
                dest=dest,
                source="auto",
                refs=[],
                editorial=True,
                skip_remote=not _remote_search_enabled(),
            )
    else:
        _path, pname = await generate_image(
            target.image_prompt or target.action,
            dest,
            refs,
            photo=not is_editorial(board.kind),
            skip_remote=not _remote_search_enabled(),
        )

    artifacts = db.artifacts_of(row)
    artifacts[target.still_id] = dest.as_posix()
    providers_raw = artifacts.get("providers")
    prov_map: dict[str, str] = {}
    if isinstance(providers_raw, str):
        with contextlib.suppress(Exception):
            parsed = json.loads(providers_raw)
            if isinstance(parsed, dict):
                prov_map = parsed
    prov_map[f"still_{target.still_id}"] = pname
    artifacts["providers"] = json.dumps(prov_map)
    _dump(job_id, "storyboard.json", board)
    db.update_job(
        job_id,
        storyboard_json=board.model_dump_json(),
        artifacts_json=json.dumps(artifacts),
    )
    return {"still_id": target.still_id, "provider": pname, "path": dest.as_posix()}


async def fill_missing_stills(
    job_id: str,
    *,
    source: str = "auto",
    force_all: bool = False,
) -> dict[str, object]:
    """Fill missing or placeholder stills across all scenes using Grok, ChatGPT, or Web Search."""
    from omaishort.providers.pollinations import looks_like_photo
    from omaishort_schema.models import Storyboard

    row = db.get_job(job_id)
    if not row or not row.get("storyboard_json"):
        raise ValueError("storyboard not ready")
    board = Storyboard.model_validate_json(row["storyboard_json"])
    artifacts = db.artifacts_of(row)
    providers_raw = artifacts.get("providers")
    prov_map: dict[str, str] = {}
    if isinstance(providers_raw, str):
        with contextlib.suppress(Exception):
            parsed = json.loads(providers_raw)
            if isinstance(parsed, dict):
                prov_map = parsed

    sdir = stills_dir(job_id)
    updated_scenes: list[int] = []
    for scene in board.scenes:
        safe_id = Path(scene.still_id).name
        dest = sdir / f"{safe_id}.png"
        prev_prov = str(prov_map.get(f"still_{scene.still_id}") or "")
        is_missing_or_placeholder = (
            not dest.is_file()
            or dest.stat().st_size < 1000
            or prev_prov in {"placeholder", "none"}
            or not looks_like_photo(dest)
        )
        if force_all or is_missing_or_placeholder:
            await regenerate_scene_still(job_id, scene.index, source=source)
            updated_scenes.append(scene.index)

    return {"updated_scenes": updated_scenes, "source": source}


async def rerender_job(job_id: str, *, regenerate_stills: bool = False) -> None:
    """Re-synthesize voiceover, captions, and MP4 from the current edited storyboard & stills."""
    from omaishort_schema.models import CharacterBible, Storyboard, StoryStructure

    row = db.get_job(job_id)
    if not row:
        return
    story = StoryInput.model_validate_json(row["input_json"])
    bible = (
        CharacterBible.model_validate_json(row["bible_json"])
        if row.get("bible_json")
        else fallback_analyze(story)[0]
    )
    structure = (
        StoryStructure.model_validate_json(row["structure_json"])
        if row.get("structure_json")
        else fallback_analyze(story)[1]
    )
    if row.get("storyboard_json"):
        board = Storyboard.model_validate_json(row["storyboard_json"])
    else:
        board = fallback_plan(story, bible, structure)
        fill_image_prompts(board, bible)

    artifacts = db.artifacts_of(row)
    sdir = stills_dir(job_id)
    sdir.mkdir(parents=True, exist_ok=True)
    rdir = refs_dir(job_id)
    loc_dir = location_refs_dir(job_id)
    prop_dir = prop_refs_dir(job_id)

    try:
        db.update_job(
            job_id,
            status=JobStatus.running.value,
            stage=JobStage.stills.value if regenerate_stills else JobStage.tts.value,
            progress="rerender:start",
            error=None,
        )
        for scene in board.scenes:
            if not (scene.image_prompt or "").strip():
                scene.image_prompt = build_scene_prompt(scene, bible)
        sourced_by_id: dict[str, Path] = {}
        if regenerate_stills and is_editorial(board.kind):
            sourced_by_id, _skind = await assign_editorial_stills(
                scenes=board.scenes,
                source_url=story.source_url,
                article_urls=None,
                captions={},
                dest_dir=sdir / "sourced",
                title=board.title or story.text[:80],
                local_paths=[],
            )
        stills: dict[str, Path] = {}
        for scene in board.scenes:
            safe_id = Path(scene.still_id).name
            dest = sdir / f"{safe_id}.png"
            if regenerate_stills or not dest.is_file():
                src_photo = sourced_by_id.get(scene.still_id)
                if src_photo and src_photo.is_file():
                    conform_photo(src_photo, dest)
                    stills[scene.still_id] = dest
                elif is_editorial(board.kind):
                    path, _pname = await resolve_scene_still(
                        prompt=scene.image_prompt or scene.action,
                        vo=scene.dialogue_or_vo,
                        title=board.title or story.text[:80],
                        dest=dest,
                        source="auto",
                        editorial=True,
                        skip_remote=not _remote_search_enabled(),
                    )
                    stills[scene.still_id] = path
                else:
                    refs = scene_still_refs(scene, refs_dir=rdir, location_dir=loc_dir, prop_dir=prop_dir)
                    path, _pname = await generate_image(
                        scene.image_prompt or scene.action,
                        dest,
                        refs,
                        photo=True,
                        skip_remote=not _remote_search_enabled(),
                    )
                    stills[scene.still_id] = path
            else:
                stills[scene.still_id] = dest
            artifacts[scene.still_id] = stills[scene.still_id].as_posix()

        db.update_job(job_id, stage=JobStage.tts.value, progress="tts", artifacts_json=json.dumps(artifacts))
        vo = join_scene_narration([scene.dialogue_or_vo for scene in board.scenes])
        voice_path, _tts_name, edge_words = await _speak_voiceover(job_id, story, vo)
        duration = probe_duration(voice_path) or float(story.target_seconds)
        board = rescale_to_audio(board, duration)
        _dump(job_id, "storyboard.json", board)
        artifacts["voiceover"] = voice_path.as_posix()

        db.update_job(
            job_id,
            stage=JobStage.captions.value,
            progress="captions",
            storyboard_json=board.model_dump_json(),
        )
        stamps, _cap_src = resolve_word_stamps(
            edge_words=edge_words,
            audio_path=voice_path,
            script=vo,
            duration=duration,
            whisper_model=WHISPER_MODEL,
        )
        ass_path = render_dir(job_id) / "captions.ass"
        style = story.subtitle or default_subtitle_style()
        words_to_ass(stamps, ass_path, style=style)
        artifacts["captions"] = ass_path.as_posix()

        db.update_job(job_id, stage=JobStage.render.value, progress="render")
        mp4 = render_dir(job_id) / "short.mp4"
        mix = story.mix or default_mix_settings()
        await compose_short(board, stills, voice_path, ass_path, mp4, render_dir(job_id), mix=mix)
        _dump(job_id, "storyboard.json", board)
        motion_path = render_dir(job_id) / "motion.json"
        i2v_ids: set[str] = set()
        if motion_path.exists():
            motion = json.loads(motion_path.read_text(encoding="utf-8"))
            i2v_ids = set(motion.get("i2v_still_ids") or [])
            artifacts["motion"] = motion_path.as_posix()
            artifacts["motion_mode"] = str(motion.get("mode") or "kenburns")
        timeline = build_timeline(board, stills, voice_path, duration, i2v_still_ids=i2v_ids)
        timeline_path = _dump(job_id, "timeline.json", timeline)
        size = probe_video_size(mp4)
        if size != (1080, 1920):
            raise RuntimeError(f"mp4 is {size}, expected 1080x1920")
        if not has_audio_stream(mp4):
            raise RuntimeError("mp4 has no audio")
        artifacts["mp4"] = mp4.as_posix()
        artifacts["timeline"] = timeline_path.as_posix()

        from omaishort.storage import inspect_job_storage

        storage_info = inspect_job_storage(job_id, row)
        storage_info["duration_sec"] = round(float(duration), 2)
        storage_info["width"] = size[0]
        storage_info["height"] = size[1]

        db.update_job(
            job_id,
            status=JobStatus.done.value,
            stage=JobStage.done.value,
            progress="done",
            storyboard_json=board.model_dump_json(),
            timeline_json=timeline.model_dump_json(),
            artifacts_json=json.dumps(artifacts),
            storage_json=json.dumps(storage_info),
            error=None,
        )
    except Exception as exc:
        db.update_job(
            job_id,
            status=JobStatus.failed.value,
            progress="failed",
            error=f"{exc}\n{traceback.format_exc()[-2000:]}",
        )
        raise
