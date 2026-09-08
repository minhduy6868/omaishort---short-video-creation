from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SubtitleStyle(BaseModel):
    font: str = "Arial"
    font_size: int = Field(default=64, ge=24, le=120)
    primary_hex: str = "#FFFFFF"
    highlight_hex: str = "#FFE000"
    outline_hex: str = "#101010"
    outline: int = Field(default=5, ge=0, le=12)
    margin_v: int = Field(default=120, ge=20, le=400)


class MixSettings(BaseModel):
    bgm_enabled: bool = True
    bgm_volume: float = Field(default=0.14, ge=0, le=1)
    duck: bool = True
    logo_enabled: bool = False
    logo_path: str | None = None
    logo_margin: int = Field(default=48, ge=8, le=200)

    @field_validator("logo_path", mode="before")
    @classmethod
    def blank_logo_path(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AssetRef(BaseModel):
    id: str
    description: str
    appearance: str = ""
    reference_image: str | None = None


class StoryMode(str, Enum):
    idea = "idea"
    script = "script"


class VideoKind(str, Enum):
    drama = "drama"
    news = "news"
    knowledge = "knowledge"
    brief = "brief"  # legacy alias of news


def is_editorial(kind: VideoKind | str | None) -> bool:
    value = kind.value if isinstance(kind, VideoKind) else str(kind or "")
    return value in {VideoKind.news.value, VideoKind.knowledge.value, VideoKind.brief.value}


def coerce_video_kind(value: object) -> object:
    if value == "brief":
        return VideoKind.news
    return value


class Genre(str, Enum):
    drama = "drama"
    confession = "confession"
    family = "family"
    cheating = "cheating"
    revenge = "revenge"
    twist = "twist"
    news = "news"
    knowledge = "knowledge"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class JobStage(str, Enum):
    queued = "queued"
    analyze = "analyze"
    plan = "plan"
    refs = "refs"
    stills = "stills"
    tts = "tts"
    captions = "captions"
    render = "render"
    done = "done"
    failed = "failed"


class Camera(str, Enum):
    wide = "wide"
    medium = "medium"
    close_up = "close_up"


class Motion(str, Enum):
    hold = "hold"
    zoom_in = "zoom_in"
    zoom_out = "zoom_out"
    pan_left = "pan_left"
    pan_right = "pan_right"


class StoryInput(BaseModel):
    mode: StoryMode = StoryMode.script
    kind: VideoKind = VideoKind.drama
    text: str = Field(min_length=8)
    target_seconds: int = Field(default=60, ge=15, le=180)
    genre: Genre = Genre.confession
    language: str = "en"
    voice_id: str | None = None
    source_url: str | None = None
    subtitle: SubtitleStyle | None = None
    mix: MixSettings | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def legacy_brief_kind(cls, value: object) -> object:
        return coerce_video_kind(value)

    @model_validator(mode="after")
    def blank_source_url(self) -> StoryInput:
        if self.source_url is not None and not self.source_url.strip():
            self.source_url = None
        if self.voice_id is not None and not self.voice_id.strip():
            self.voice_id = None
        if self.kind == VideoKind.news and self.genre in {
            Genre.confession,
            Genre.cheating,
            Genre.revenge,
            Genre.twist,
            Genre.family,
            Genre.drama,
        }:
            self.genre = Genre.news
        if self.kind == VideoKind.knowledge and self.genre not in {Genre.knowledge, Genre.news}:
            self.genre = Genre.knowledge
        return self


class Character(BaseModel):
    id: str
    age: int | None = None
    gender: str | None = None
    appearance: str
    clothing: str
    personality: str = ""
    voice_id: str | None = None
    reference_image: str | None = None


class CharacterBible(BaseModel):
    characters: list[Character] = Field(min_length=1)
    locations: list[AssetRef] = Field(default_factory=list)
    props: list[AssetRef] = Field(default_factory=list)


class StoryStructure(BaseModel):
    hook: str
    conflict: str
    rising_action: str
    twist: str
    ending: str
    hook_sec: float = 6
    conflict_sec: float = 12
    rising_sec: float = 20
    twist_sec: float = 14
    ending_sec: float = 8


class Shot(BaseModel):
    camera: Camera
    motion: Motion
    t_start: float
    t_end: float
    still_id: str

    @model_validator(mode="after")
    def end_after_start(self) -> Shot:
        if self.t_end <= self.t_start:
            raise ValueError("t_end must be greater than t_start")
        return self


class Scene(BaseModel):
    index: int
    duration_sec: float = Field(gt=0)
    location: str
    location_id: str | None = None
    characters: list[str]
    prop_ids: list[str] = Field(default_factory=list)
    emotion: str
    action: str
    dialogue_or_vo: str
    lighting: str
    mood: str
    consistency_notes: str = ""
    still_id: str
    shots: list[Shot] = Field(min_length=1)
    image_prompt: str = ""
    use_face_ref: bool = True
    use_location_ref: bool = True
    speaker_id: str | None = None

    @model_validator(mode="after")
    def shots_share_still(self) -> Scene:
        for shot in self.shots:
            if shot.still_id != self.still_id:
                raise ValueError("every shot in a scene must share the scene still_id")
        return self


class Storyboard(BaseModel):
    title: str
    target_seconds: float
    language: str = "en"
    kind: VideoKind = VideoKind.drama
    scenes: list[Scene] = Field(min_length=1)

    @field_validator("kind", mode="before")
    @classmethod
    def legacy_brief_kind(cls, value: object) -> object:
        return coerce_video_kind(value)

    @model_validator(mode="after")
    def unique_stills_per_scene(self) -> Storyboard:
        stills = [s.still_id for s in self.scenes]
        if len(stills) != len(set(stills)):
            raise ValueError("each scene must have its own still_id")
        return self


class TimelineElement(BaseModel):
    id: str
    type: Literal["image", "video"] = "image"
    src: str
    from_sec: float
    duration_sec: float
    animation: str
    camera: str = "medium"
    enter: str = "fade"


class TimelineText(BaseModel):
    text: str
    from_sec: float
    duration_sec: float


class TimelineAudio(BaseModel):
    src: str
    from_sec: float = 0
    duration_sec: float


class Timeline(BaseModel):
    shortTitle: str
    width: int = 1080
    height: int = 1920
    fps: int = 30
    elements: list[TimelineElement]
    text: list[TimelineText]
    audio: list[TimelineAudio]
