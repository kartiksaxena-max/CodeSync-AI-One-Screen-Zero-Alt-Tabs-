"""Index a lesson video: find when each line of code first appears on screen.

    python tools/index_video.py sample-loops [--every 1.0]

Reads lessons/<id>/video.mp4, runs the same OCR + cleanup used by live capture
on frames that changed, and writes lessons/<id>/code_timeline.json. That file
is what lets a student click a line of code and jump to the moment the teacher
wrote it. Uses the crop in lesson.json ("capture_crop") to look only at the
teacher's code area.
"""
import argparse
import difflib
import json
import sys
import time
from pathlib import Path

import cv2
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import codecap, engines, lessons  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lesson")
    ap.add_argument("--every", type=float, default=1.0, help="seconds between sampled frames")
    ap.add_argument("--engine", default="auto", choices=["auto", "cpu", "npu"])
    args = ap.parse_args()

    les = lessons.get(args.lesson)
    pack = Path(les["_dir"])
    x0, y0, x1, y1 = les.get("capture_crop", [0, 0, 1, 1])
    eng = engines.get_ocr(args.engine)
    cap = cv2.VideoCapture(str(pack / les["video"]))
    fps = cap.get(cv2.CAP_PROP_FPS) or 10
    total = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps

    seen: list[tuple[str, float]] = []
    prev_gray, ocr_calls, t = None, 0, 0.0
    started = time.time()
    while t < total:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        crop = frame[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        changed = prev_gray is None or cv2.absdiff(gray, prev_gray).mean() > 0.03
        prev_gray = gray
        if changed:
            ocr_calls += 1
            img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            boxes, _ = eng.run(img)
            for line in codecap.boxes_to_code(boxes, les["_vocab"])["lines"]:
                text = line["text"]
                if line.get("blank") or not codecap.looks_like_code(text):
                    continue
                if any(difflib.SequenceMatcher(None, text, s).ratio() > 0.92 for s, _ in seen):
                    continue
                seen.append((text, round(t, 1)))
        t += args.every
    timeline = [{"time": at, "text": text} for text, at in sorted(seen, key=lambda s: s[1])]
    (pack / "code_timeline.json").write_text(json.dumps(timeline, indent=2))
    print(f"{len(timeline)} lines found, {ocr_calls} frames OCR'd of {int(total / args.every)} sampled, "
          f"{time.time() - started:.0f}s, engine={eng.mode}")
    for e in timeline:
        print(f"  {e['time']:>5}s  {e['text']}")


if __name__ == "__main__":
    main()
