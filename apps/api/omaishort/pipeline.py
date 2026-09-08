from __future__ import annotations

import json
import traceback
from pathlib import Path

from omaishort import db
from omaishort.config import WHISPER_MODEL, default_mix_settings, default_subtitle_style
from omaishort.engine.analyzer import analyze_story, write_knowledge_script
from omaishort.engine.brief_media import (
    assign_editorial_stills,
    conform_photo,
    fetch_article,
    fetch_github_project,
    fetch_knowledge_topic,
    is_knowledge_topic,
    looks_like_github,
    looks_like_url,
    prefer_readme_language,
)
from omaishort.engine.fallback import clamp_brief_storyboard, fallback_analyze, fallback_plan
from omaishort.engine.captions import resolve_word_stamps, words_to_ass
from omaishort.engine.compose import compose_short
from omaishort.engine.image_prompts import build_location_prompt, build_prop_prompt, build_ref_prompt, fill_image_prompts
from omaishort.engine.planner import plan_scenes
from omaishort.engine.rescale import rescale_to_audio
from omaishort.engine.timeline import build_timeline
from omaishort.paths import audio_dir, job_dir, location_refs_dir, prop_refs_dir, refs_dir, render_dir, stills_dir
from omaishort.providers.image import generate_image
from omaishort.providers.tts import join_scene_narration, silence_audio, synthesize_speech
from omaishort.engine.kenburns import has_audio_stream, probe_duration, probe_video_size
from omaishort_schema.models import Genre, JobStage, JobStatus, StoryInput, VideoKind, is_editorial


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
                    if page.text and len(page.text) >= 8:
                        story = story.model_copy(update={"text": page.text})
                article_urls = page.image_urls
                article_captions = page.image_captions
                artifacts["source_url"] = story.source_url
                providers["article"] = f"{len(article_urls)} photos"
            except Exception as exc:
                providers["article"] = f"fetch_failed:{type(exc).__name__}"
        elif story.kind == VideoKind.knowledge and is_knowledge_topic(story.text):
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
            db.update_job(job_id, artifacts_json=json.dumps(artifacts), progress="script")
        db.update_job(job_id, status=JobStatus.running.value, stage=JobStage.analyze.value, progress="analyze")
        if providers.get("script") in {"llm", "chatgpt-web"}:
            bible, structure = fallback_analyze(story)
            src = "script"
        else:
            bible, structure, src = await analyze_story(story)
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
        providers["planner"] = plan_src
        if is_editorial(story.kind):
            clamp_brief_storyboard(board, story.target_seconds, story.language)
        _dump(job_id, "storyboard.json", board)
        db.update_job(job_id, storyboard_json=board.model_dump_json(), stage=JobStage.refs.value, progress="refs")

        rdir = refs_dir(job_id)
        loc_dir = location_refs_dir(job_id)
        prop_dir = prop_refs_dir(job_id)
        if not is_editorial(story.kind):
            for char in bible.characters:
                dest = rdir / f"{char.id}.png"
                prompt = build_ref_prompt(char)
                path, pname = await generate_image(prompt, dest, photo=True)
                providers[f"ref_{char.id}"] = pname
                char.reference_image = path.as_posix()
                artifacts[f"ref_{char.id}"] = path.as_posix()
            for loc in bible.locations:
                dest = loc_dir / f"{loc.id}.png"
                prompt = build_location_prompt(loc)
                path, pname = await generate_image(prompt, dest, skip_remote=True)
                providers[f"loc_{loc.id}"] = pname
                loc.reference_image = path.as_posix()
                artifacts[f"loc_{loc.id}"] = path.as_posix()
            for prop in bible.props:
                dest = prop_dir / f"{prop.id}.png"
                prompt = build_prop_prompt(prop)
                path, pname = await generate_image(prompt, dest, skip_remote=True)
                providers[f"prop_{prop.id}"] = pname
                prop.reference_image = path.as_posix()
                artifacts[f"prop_{prop.id}"] = path.as_posix()
        else:
            providers["refs"] = "skipped_brief"
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
            sourced_by_id, source_kind = await assign_editorial_stills(
                scenes=board.scenes,
                source_url=story.source_url,
                article_urls=article_urls,
                captions=article_captions,
                dest_dir=sdir / "sourced",
                title=board.title or story.text[:80],
            )
            providers["brief_stills"] = source_kind
        for scene in board.scenes:
            dest = sdir / f"{scene.still_id}.png"
            refs: list[Path] = []
            src = sourced_by_id.get(scene.still_id)
            if not src and sourced_by_id:
                pool = list(dict.fromkeys(sourced_by_id.values()))
                src = pool[len(stills) % len(pool)]
            if src:
                conform_photo(src, dest)
                path, pname = dest, source_kind
            elif is_editorial(story.kind):
                path, pname = await generate_image(scene.image_prompt, dest, skip_remote=True)
            else:
                if scene.use_face_ref:
                    for cid in scene.characters:
                        ref = rdir / f"{cid}.png"
                        if ref.exists():
                            refs.append(ref)
                path, pname = await generate_image(scene.image_prompt, dest, refs, photo=True)
            providers[f"still_{scene.still_id}"] = pname
            stills[scene.still_id] = path
            artifacts[scene.still_id] = path.as_posix()
            db.update_job(job_id, artifacts_json=json.dumps(artifacts), progress=f"stills:{scene.still_id}")

        db.update_job(job_id, stage=JobStage.tts.value, progress="tts")
        vo = join_scene_narration([scene.dialogue_or_vo for scene in board.scenes])
        voice_path = audio_dir(job_id) / "voiceover.mp3"
        edge_words = None
        try:
            tts = await synthesize_speech(vo, voice_path, story.language, story.voice_id)
            voice_path = tts.path
            providers["tts"] = tts.provider
            edge_words = tts.words
        except Exception:
            seconds = max(story.target_seconds, len(vo.split()) / 2.5)
            voice_path = await silence_audio(audio_dir(job_id) / "voiceover.mp3", seconds)
            providers["tts"] = "silence"
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
        providers["captions"] = cap_src
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
        artifacts["providers"] = json.dumps(providers)

        db.update_job(
            job_id,
            status=JobStatus.done.value,
            stage=JobStage.done.value,
            progress="done",
            timeline_json=timeline.model_dump_json(),
            artifacts_json=json.dumps(artifacts),
            error=None,
        )
    except Exception as exc:
        db.update_job(
            job_id,
            status=JobStatus.failed.value,
            stage=JobStage.failed.value,
            progress="failed",
            error=f"{exc}\n{traceback.format_exc()[-2000:]}",
        )
        raise
