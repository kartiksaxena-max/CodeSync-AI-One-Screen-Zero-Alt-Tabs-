"""CodeSync AI local server.  Run:  python -m uvicorn backend.app:app --port 8000"""
from __future__ import annotations

import io
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel

from . import codecap, engines, lessons, runner, search

ROOT = Path(__file__).resolve().parent.parent
BENCH_FILE = ROOT / "benchmarks" / "last_run.json"
STARTED = time.time()

app = FastAPI(title="CodeSync AI", docs_url="/api/docs", openapi_url="/api/openapi.json")
STATS: dict = {"last_ocr": None}


def _lesson(lesson_id: str) -> dict:
    try:
        return lessons.get(lesson_id)
    except KeyError:
        raise HTTPException(404, f"lesson '{lesson_id}' not found")


@app.get("/api/lessons")
def list_lessons():
    return lessons.list_all()


@app.get("/api/lessons/{lesson_id}")
def get_lesson(lesson_id: str):
    return lessons.public(_lesson(lesson_id))


@app.post("/api/capture")
async def capture(
    file: UploadFile = File(...),
    lesson: str = Form(...),
    t: float = Form(0.0),
    crop: str = Form(""),          # "x0,y0,x1,y1" as fractions of the frame
    engine: str = Form("auto"),    # auto | cpu | npu
    low_resource: bool = Form(False),
):
    """Code-from-video: OCR a paused video frame and return clean, indented code
    with the moment the teacher wrote each line."""
    les = _lesson(lesson)
    img = Image.open(io.BytesIO(await file.read())).convert("RGB")
    if crop:
        try:
            x0, y0, x1, y1 = [float(v) for v in crop.split(",")]
            w, h = img.size
            img = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        except ValueError:
            raise HTTPException(400, "crop must be four comma-separated numbers between 0 and 1")
    if low_resource:
        img.thumbnail((960, 960))
    try:
        eng = engines.get_ocr(engine)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    boxes, ms = eng.run(img)
    result = codecap.boxes_to_code(boxes, les["_vocab"])
    lessons.link_lines(result["lines"], les, t)
    STATS["last_ocr"] = {"engine": eng.mode, "ms": round(ms), "at": datetime.now(timezone.utc).isoformat()}
    return {**result, "engine": eng.mode, "ocr_ms": round(ms), "providers": eng.session_providers(),
            "image_size": list(img.size)}


class SearchIn(BaseModel):
    lesson: str
    q: str


@app.post("/api/search")
def do_search(body: SearchIn):
    return search.search(_lesson(body.lesson), body.q)


class RunIn(BaseModel):
    code: str
    lesson: str | None = None
    checkpoint: int | None = None


@app.post("/api/run")
def run(body: RunIn):
    res = runner.run_code(body.code)
    res["explain"] = _explain(res["stderr"], body.lesson)
    return res


@app.post("/api/check")
def check(body: RunIn):
    les = _lesson(body.lesson or "")
    cps = les.get("checkpoints", [])
    if body.checkpoint is None or not (0 <= body.checkpoint < len(cps)):
        raise HTTPException(400, "unknown checkpoint")
    res = runner.check(body.code, cps[body.checkpoint])
    res["explain"] = _explain(res["stderr"], body.lesson)
    return res


def _explain(stderr: str, lesson_id: str | None):
    info = runner.explain(stderr) if stderr and "Stopped after" not in stderr else None
    if info and lesson_id and info.get("query"):
        info["related"] = search.search(_lesson(lesson_id), info["query"], limit=2)
    return info


@app.get("/api/hardware")
def hardware():
    info = engines.system_info()
    info["uptime_s"] = round(time.time() - STARTED)
    info["last_ocr"] = STATS["last_ocr"]
    info["last_benchmark"] = json.loads(BENCH_FILE.read_text()) if BENCH_FILE.exists() else None
    return info


class BenchIn(BaseModel):
    lesson: str = "sample-loops"
    runs: int = 8


@app.post("/api/benchmark")
def benchmark(body: BenchIn):
    """Time the same OCR job on each available engine. Every number is measured
    on this machine right now. Power draw is not measured by this app: use the
    Windows/Qualcomm tools described in docs/BENCHMARKING.md."""
    les = _lesson(body.lesson)
    img = Image.open(Path(les["_dir"]) / "bench_frame.png").convert("RGB")
    runs = max(3, min(body.runs, 30))
    before = engines.system_info().get("battery_percent")
    rows = {}
    for mode in ("cpu", "npu"):
        if mode == "npu" and not engines.npu_available():
            rows[mode] = {"available": False,
                          "reason": "QNNExecutionProvider not present in this onnxruntime build "
                                    "(needs onnxruntime-qnn on a Snapdragon X Windows ARM64 laptop)"}
            continue
        try:
            eng = engines.get_ocr(mode)
            eng.run(img)  # warm-up, not counted
            times = [eng.run(img)[1] for _ in range(runs)]
            times_sorted = sorted(times)
            rows[mode] = {
                "available": True, "runs": runs, "load_ms": round(eng.load_ms),
                "mean_ms": round(statistics.mean(times)), "median_ms": round(statistics.median(times)),
                "min_ms": round(times_sorted[0]), "p95_ms": round(times_sorted[int(0.95 * (runs - 1))]),
                "providers": eng.session_providers(),
            }
        except Exception as e:  # report failures instead of hiding them
            rows[mode] = {"available": False, "reason": f"{type(e).__name__}: {e}"}
    out = {
        "at": datetime.now(timezone.utc).isoformat(),
        "task": "OCR of one 1280x466 code frame (detect + recognise), RapidOCR PP-OCR models via ONNX Runtime",
        "system": engines.system_info(),
        "battery_before": before, "battery_after": engines.system_info().get("battery_percent"),
        "results": rows,
    }
    BENCH_FILE.parent.mkdir(exist_ok=True)
    BENCH_FILE.write_text(json.dumps(out, indent=2))
    return out


app.mount("/lessons", StaticFiles(directory=ROOT / "lessons"), name="lessons")
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")
