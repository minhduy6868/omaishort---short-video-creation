from __future__ import annotations

import json
import traceback
from pathlib import Path

from omaishort import db
from omaishort.config import WHISPER_MODEL, default_mix_settings, default_subtitle_style
from omaishort.engine.analyzer import analyze_story
from omaishort.engine.captions import resolve_word_stamps, words_to_ass
from omaishort.engine.compose import compose_short
from omaishort.engine.image_prompts import build_location_prompt, build_prop_prompt, build_ref_prompt, fill_image_prompts
from omaishort.engine.planner import plan_scenes
from omaishort.engine.rescale import rescale_to_audio
from omaishort.engine.timeline import build_timeline
from omaishort.paths import audio_dir, job_dir, location_refs_dir, prop_refs_dir, refs_dir, render_dir, stills_dir
from omaishort.providers.image import generate_image
from omaishort.providers.tts import silence_audio, synthesize_speech
from omaishort.engine.kenburns import has_audio_stream, probe_duration, probe_video_size
from omaishort_schema.models import JobStage, JobStatus, StoryInput


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
    try:
        db.update_job(job_id, status=JobStatus.running.value, stage=JobStage.analyze.value, progress="analyze")
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

        board, plan_src = await plan_scenes(story, bible, structure)
        providers["planner"] = plan_src
        _dump(job_id, "storyboard.json", board)
        db.update_job(job_id, storyboard_json=board.model_dump_json(), stage=JobStage.refs.value, progress="refs")

        rdir = refs_dir(job_id)
        loc_dir = location_refs_dir(job_id)
        prop_dir = prop_refs_dir(job_id)
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
        for scene in board.scenes:
            dest = sdir / f"{scene.still_id}.png"
            refs: list[Path] = []
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
        vo = " ".join(scene.dialogue_or_vo.strip() for scene in board.scenes)
        voice_path = audio_dir(job_id) / "voiceover.mp3"
        edge_words = None
        try:
            tts = await synthesize_speech(vo, voice_path, story.language)
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
