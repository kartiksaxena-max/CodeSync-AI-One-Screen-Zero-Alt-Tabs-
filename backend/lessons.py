"""Lesson packs: a folder with lesson.json, a video, slide images and an optional
code_timeline.json (when each line of code first appeared on the teacher's screen)."""
from __future__ import annotations

import json
from pathlib import Path

from . import codecap

LESSON_DIR = Path(__file__).resolve().parent.parent / "lessons"
_cache: dict[str, dict] = {}


def _load(pack: Path) -> dict:
    lesson = json.loads((pack / "lesson.json").read_text(encoding="utf-8"))
    tl = pack / "code_timeline.json"
    lesson["code_timeline"] = json.loads(tl.read_text(encoding="utf-8")) if tl.exists() else []
    text = " ".join(s["text"] for s in lesson["transcript"]) + " " + " ".join(s["text"] for s in lesson["slides"])
    lesson["_vocab"] = codecap.build_vocab(text)
    lesson["_dir"] = str(pack)
    return lesson


def get(lesson_id: str) -> dict:
    if lesson_id not in _cache:
        pack = LESSON_DIR / lesson_id
        if not (pack / "lesson.json").exists():
            raise KeyError(lesson_id)
        _cache[lesson_id] = _load(pack)
    return _cache[lesson_id]


def list_all() -> list[dict]:
    out = []
    for p in sorted(LESSON_DIR.iterdir()):
        if (p / "lesson.json").exists():
            l = get(p.name)
            out.append({"id": l["id"], "title": l["title"], "duration": l["duration"]})
    return out


def public(lesson: dict) -> dict:
    return {k: v for k, v in lesson.items() if not k.startswith("_")}


def link_lines(lines: list[dict], lesson: dict, capture_time: float) -> None:
    """Attach the moment the teacher wrote each captured line (two-way video<->code link)."""
    import difflib

    entries = [(e["text"].strip(), e["time"]) for e in lesson["code_timeline"]]
    for line in lines:
        if line.get("blank"):
            line["time"], line["link"] = None, None
            continue
        want = line["text"].strip()
        best, best_score = None, 0.0
        for text, t in entries:
            score = 1.0 if text == want else difflib.SequenceMatcher(None, text, want).ratio()
            if score > best_score:
                best, best_score = t, score
        if best is not None and best_score >= 0.85:
            line["time"], line["link"] = best, "indexed"
        else:
            line["time"], line["link"] = round(capture_time, 1), "capture"
