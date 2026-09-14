from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from omaishort.engine.apply_attachments import apply_attachment_files
from omaishort.engine.brief_media import assign_editorial_stills
from omaishort_schema.models import AssetRef, Character, CharacterBible, VideoKind
from omaishort_schema.models import Scene, Shot


def _png(path: Path, color: tuple[int, int, int] = (200, 40, 40)) -> Path:
    Image.new("RGB", (64, 96), color).save(path, "PNG")
    return path


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path, monkeypatch):
    import omaishort.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)



def _bible() -> CharacterBible:
    return CharacterBible(
        characters=[
            Character(id="wife", appearance="dark hair", clothing="robe"),
            Character(id="narrator", appearance="voice", clothing="n/a"),
        ],
        locations=[AssetRef(id="kitchen", description="kitchen")],
        props=[AssetRef(id="phone", description="phone")],
    )


def test_face_attachment_writes_passport(tmp_path: Path):
    src = _png(tmp_path / "wife.png")
    applied = apply_attachment_files(
        "jobface01",
        VideoKind.drama.value,
        _bible(),
        [{"kind": "face", "bind": "wife", "filename": "wife.png", "path": src}],
    )
    dest = applied.faces["wife"]
    assert dest.is_file()
    assert dest.name == "wife.png"


def test_editorial_ignored_on_drama(tmp_path: Path):
    src = _png(tmp_path / "news.png", (10, 80, 20))
    applied = apply_attachment_files(
        "jobdramaed",
        VideoKind.drama.value,
        _bible(),
        [{"kind": "editorial", "bind": None, "filename": "news.png", "path": src}],
    )
    assert applied.editorial == []
    assert applied.faces == {}


def test_face_ignored_on_news(tmp_path: Path):
    src = _png(tmp_path / "face.png")
    applied = apply_attachment_files(
        "jobnewsf",
        VideoKind.news.value,
        _bible(),
        [{"kind": "face", "bind": "wife", "filename": "face.png", "path": src}],
    )
    assert applied.faces == {}


def test_editorial_local_stills_win(tmp_path: Path):
    import asyncio

    photo = _png(tmp_path / "beat.png", (30, 30, 180))
    scene = Scene(
        index=1,
        duration_sec=8,
        location="studio",
        characters=[],
        emotion="hook",
        action="desk",
        dialogue_or_vo="Headline about a policy change in Hanoi.",
        lighting="broadcast",
        mood="hook",
        still_id="still_01",
        shots=[Shot(camera="medium", motion="zoom_in", t_start=0, t_end=8, still_id="still_01")],
        use_face_ref=False,
    )
    dest = tmp_path / "sourced"
    out, kind = asyncio.run(
        assign_editorial_stills(
            scenes=[scene],
            source_url=None,
            article_urls=[],
            dest_dir=dest,
            title="policy",
            local_paths=[photo],
        )
    )
    assert kind == "attachment"
    assert "still_01" in out
    assert out["still_01"].is_file()


def test_logo_and_script_copy(tmp_path: Path):
    logo = _png(tmp_path / "mark.png", (255, 255, 255))
    script = tmp_path / "notes.md"
    script.write_text("hello world this is a drama story", encoding="utf-8")
    applied = apply_attachment_files(
        "joblogo01",
        VideoKind.drama.value,
        _bible(),
        [
            {"kind": "logo", "bind": None, "filename": "mark.png", "path": logo},
            {"kind": "script", "bind": None, "filename": "notes.md", "path": script},
        ],
    )
    assert applied.logo and applied.logo.is_file()
    assert applied.script and "hello world" in applied.script.read_text(encoding="utf-8")
