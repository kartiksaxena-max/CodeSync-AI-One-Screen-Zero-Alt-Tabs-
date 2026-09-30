"""UNTESTED starting point: make a transcript for a lesson video with Whisper.

    python tools/transcribe.py lessons/my-lesson/video.mp4

Not run in the development sandbox (no model download access there). It uses
faster-whisper on the CPU and prints segments in the lesson.json format
({"start", "end", "text"}). The Snapdragon plan is to swap this for a Whisper
model from Qualcomm AI Hub run through ONNX Runtime QNN; that part is not built.
"""
import json
import sys

try:
    from faster_whisper import WhisperModel  # pip install faster-whisper
except ImportError:
    sys.exit("pip install faster-whisper first")

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe(sys.argv[1], vad_filter=True)
out = [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()} for s in segments]
print(json.dumps(out, indent=2, ensure_ascii=False))
