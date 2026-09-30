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

## Run it

```
run.bat        # Windows
./run.sh       # macOS / Linux
```

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

```
backend/   FastAPI server: engines.py (ONNX Runtime providers), codecap.py (frame to code),
           search.py, runner.py, lessons.py, app.py
web/       index.html, app.css, app.js (no external files, works offline)
lessons/   lesson packs (sample-loops: video, slides, lesson.json, code_timeline.json)
tools/     make_sample_pack.py, index_video.py, transcribe.py (untested)
docs/      ARCHITECTURE.md, BENCHMARKING.md, DEMO_SCRIPT.md, EVIDENCE.md
```

## Adding a lesson

Make a folder in `lessons/` with `lesson.json`, `video.mp4` and slide images (copy `sample-loops` as a template). Set `capture_crop` to the part of the video where the teacher's code appears. Then run `python tools/index_video.py <lesson-id>`.

## Submission checklist (Unstop "Solution Submission Round")

- [ ] Project title
- [ ] Brief project description (PDF, DOC or DOCX)
- [ ] This repository's link, public
- [ ] Short pitch presentation as PDF
- [ ] The same presentation as PPTX
- [ ] Snapdragon laptop questions: answer truthfully
