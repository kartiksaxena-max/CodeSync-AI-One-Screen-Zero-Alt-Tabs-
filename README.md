# CodeSync AI: one screen, zero alt-tabs

An offline coding classroom for students learning on modest laptops. The teacher's video, slides and transcript sit next to your code editor in one window. AI that runs on the laptop turns what the teacher types on screen into code you can use.

Built for the Snapdragon® AI Lab Build & Present Challenge (Qualcomm, via Unstop).

## The problem

Following a coding tutorial means a video in one window, slides or a book in another, and an editor in a third. Every switch loses your place. Many students in India learn on laptops with weak internet, so cloud tools are not always an option.

## What it does

- **Code from video.** Pause on the teacher's code, drag over it, and the app reads the frame with OCR, rebuilds the indentation and blank lines, fixes likely misreads using the lesson's own words (for example `total marks` becomes `total_marks`), and adds the code to your editor.
- **Two-way link between video and code.** Each captured line remembers when the teacher first wrote it. Click the time chip on a line and the video jumps there. The moments are found ahead of time by `tools/index_video.py`.
- **Everything in one window.** Video, slides that follow the video, and a transcript you can click. English or Hindi captions.
- **Search across the lesson.** One search covers the transcript, the slides and the teacher's code.
- **Checkpoints and hints.** The video pauses at a checkpoint. Hints come in three steps. Errors are explained in plain language and point to the part of the lesson that covers them.
- **Runs offline.** No cloud calls. A low-resource mode uses smaller frames for older laptops.
- **Engine panel.** Shows which ONNX Runtime providers are present, and times the same task on CPU and NPU on the machine it is running on.

## How it works (workflow)

**Student workflow, end to end:**

1. **Open a lesson.** The app loads a lesson pack (video + slides + transcript + checkpoints) into one window.
2. **Watch and read together.** The video plays on the left; the transcript auto-scrolls and highlights the current line; slides advance in sync with the video timestamp.
3. **Pause and capture code.** When the teacher writes code on screen, the student pauses, drags a box over it, and clicks Capture. The frame is sent to the local OCR engine, cleaned up, and dropped into the editor — no retyping, no alt-tabbing.
4. **Code stays linked to the lesson.** Every captured (or typed) line can carry a "time chip." Clicking it jumps the video back to the moment that line was taught. This link is two-way: video to code, and code to video.
5. **Search anytime.** A single search box queries the transcript, slide text, and the teacher's captured code together, so "why do I need four spaces" surfaces the right transcript moment even if the student never saw a slide about indentation.
6. **Hit a checkpoint.** The video pauses automatically at a marked point. The student attempts the task in the editor, clicks Check, and gets pass/fail feedback plus a three-level hint ladder (nudge → bigger hint → solution) if they're stuck.
7. **Run and debug.** Code runs locally in a subprocess with a timeout. Errors are translated into plain-language explanations and linked back to the exact lesson segment that explains the concept.
8. **Everything stays on-device.** No lesson content, code, or captures leave the laptop. The engine panel shows which hardware (CPU or Snapdragon NPU) actually served the last request, with real, measured timings — not marketing numbers.

**Teacher / content workflow (offline, ahead of time):**

1. Record or reuse a screen-recording video of the coding lesson.
2. Write (or eventually auto-generate) a transcript and slide deck.
3. Run `tools/index_video.py` once on the video — it OCRs the recording and builds `code_timeline.json`, recording the moment each line of code first appeared. This is what powers the two-way video↔code link for every student who later uses the pack.
4. Drop the video, slides, transcript, and checkpoints into a `lesson.json` following the `sample-loops` template, and the pack is ready to distribute (as a folder or zip) to students — no server, no account, no internet required.

## Architecture
─ Browser (single window) ────────────────────────────────┐
│ │
│ ┌───────────────────────┐ ┌────────────────────────────────────────────────────┐ │
│ │ Lesson pane │ │ Work pane │ │
│ │ video · transcript │ │ code editor · time-linked lines · run output │ │
│ │ slides · search │◄─►│ checkpoint / hint cards · capture sheet │ │
│ └───────────┬─────────────┘ └───────────────────┬────────────────────────────────┘ │
│ │ frame capture (paused video, cropped)│ run / check code │
└───────────────┼────────────────────────────────────┼──────────────────────────────────────┘
│ POST /api/capture │ POST /api/run, /api/check
▼ ▼
┌───────────────────────────────────────────────────────────┐
│ Local FastAPI server (backend/) │
│ │
│ app.py – routes: lessons, capture, search, run, │
│ check, hardware, benchmark │
│ engines.py – OCR session mgmt, CPU/NPU provider select │
│ codecap.py – OCR boxes → clean, indented, typo-fixed │
│ code (uses lesson vocabulary) │
│ search.py – TF-IDF search across transcript/slides/code│
│ runner.py – sandboxed-timeout code execution + plain- │
│ language error explanations │
│ lessons.py – loads lesson.json, links captured lines to │
│ code_timeline.json via fuzzy match │
└───────────────┬─────────────────────────────┬───────────────┘
│ │
▼ ▼
┌────────────────────┐ ┌──────────────────────┐
│ ONNX Runtime │ │ lessons/ (data) │
│ (RapidOCR models) │ │ video.mp4, slides/, │
│ │ │ lesson.json, │
│ CPUExecutionProv. │ │ code_timeline.json │
│ QNNExecutionProv. │◄── tools/index_video.py builds │
│ (Snapdragon NPU, │ the timeline once, offline │
│ when available) │ │
└────────────────────┘ └──────────────────────┘
****

**Design choices worth noting:**
- **Everything is local.** The browser talks only to `localhost:8000`; the server never calls out to the internet. This is what makes the tool usable on weak or no connectivity.
- **The OCR engine is provider-agnostic.** `engines.py` asks ONNX Runtime for whichever execution providers are available and reports back what was actually used — CPU everywhere, and the Qualcomm NPU (`QNNExecutionProvider`) automatically when the app runs on a Snapdragon laptop with `onnxruntime-qnn` installed. There is no separate code path per device.
- **The video↔code link is precomputed, not live.** `tools/index_video.py` runs once per lesson (by the teacher/content creator) so that students get instant, indexed jumps instead of re-running OCR on the whole video every session.
- **Search, run, and capture are separate, composable endpoints** (see `backend/app.py`), so any of them can be swapped for a stronger on-device model later (e.g. TF-IDF search → an embedding model from Qualcomm AI Hub) without touching the others.

## Run it
run.bat # Windows
./run.sh # macOS / Linux

Then open http://localhost:8000. Needs Python 3.10, 3.11 or 3.12 (the OCR package does not support 3.13 or newer yet).

**On a Snapdragon X laptop** use the ARM64 build of Python, then:
`pip uninstall -y onnxruntime` and `pip install onnxruntime-qnn`.
The chip in the top right will then report the NPU provider. See [docs/BENCHMARKING.md](docs/BENCHMARKING.md) to record real numbers.

## Honest status

Tested in a Linux x86 development sandbox on the CPU only:

| Part | Status |
|---|---|
| Code capture: OCR, indentation, blank lines, gutter removal, typo repair | Works on the sample lesson (10 of 10 lines exact) |
| Video indexing to `code_timeline.json` | Works, matches the times the sample video was built with |
| Click-a-line-to-jump-video links | Works (logic tested headlessly) |
| Transcript, slides, search, notes, run, error explanations, checkpoint, hints, Hindi captions | Work (logic tested headlessly against the running server) |
| Engine panel and benchmark endpoint | Work on CPU. The NPU column reports "not available" without the QNN provider. |

Not done or not verified:

| Part | Status |
|---|---|
| Running on the Snapdragon NPU | Wired up, **not yet tested on a Snapdragon laptop**. The OCR models are not compiled or quantised for the NPU, so results may show CPU fallback. No NPU numbers are claimed. |
| Layout in a real browser | Not viewed yet. Only the page logic was tested. Check it on your laptop. |
| Sample lesson | Synthetic: silent video, authored transcript (English and Hindi). Not speech-to-text output. |
| Whisper transcripts on the NPU | Not built. `tools/transcribe.py` is an untested CPU starting point. |
| On-device LLM, embedding search, auto chapters, quizzes, lesson pack builder, class progress | Roadmap |

The code runner starts your code as a normal local process with a 5 second limit. It is not a hardened sandbox. Do not expose the server to other people's networks.

## Layout
backend/ FastAPI server: engines.py (ONNX Runtime providers), codecap.py (frame to code),
search.py, runner.py, lessons.py, app.py
web/ index.html, app.css, app.js (no external files, works offline)
lessons/ lesson packs (sample-loops: video, slides, lesson.json, code_timeline.json)
tools/ make_sample_pack.py, index_video.py, transcribe.py (untested)
docs/ ARCHITECTURE.md, BENCHMARKING.md, DEMO_SCRIPT.md, EVIDENCE.md

## Adding a lesson

Make a folder in `lessons/` with `lesson.json`, `video.mp4` and slide images (copy `sample-loops` as a template). Set `capture_crop` to the part of the video where the teacher's code appears. Then run `python tools/index_video.py <lesson-id>`.
