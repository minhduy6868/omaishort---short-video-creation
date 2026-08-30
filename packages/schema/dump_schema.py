from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from omaishort_schema.models import (
    CharacterBible,
    Scene,
    Storyboard,
    StoryInput,
    StoryStructure,
    Timeline,
)

OUT = Path(__file__).resolve().parent / "json"
OUT.mkdir(parents=True, exist_ok=True)

models = {
    "story_input": StoryInput,
    "character_bible": CharacterBible,
    "story_structure": StoryStructure,
    "scene": Scene,
    "storyboard": Storyboard,
    "timeline": Timeline,
}

for name, model in models.items():
    (OUT / f"{name}.schema.json").write_text(
        json.dumps(model.model_json_schema(), indent=2),
        encoding="utf-8",
    )
