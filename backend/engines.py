"""On-device inference engines.

Everything AI-related goes through ONNX Runtime so the same code can run on the
CPU or, on a Snapdragon X laptop, be offered to the Qualcomm NPU through the
QNN execution provider (package `onnxruntime-qnn`, Windows on ARM64).

Honesty rule used everywhere in this project: we report the execution
providers a session was *actually created with*, and every timing is measured,
never assumed. A provider being registered does not prove every operator ran
on the NPU: unsupported operators fall back to the CPU inside ONNX Runtime.
"""
from __future__ import annotations

import os
import platform
import threading
import time
from typing import Any

import numpy as np
import onnxruntime as ort
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from rapidocr_onnxruntime.utils import infer_engine as _ie

QNN = "QNNExecutionProvider"
_mode_lock = threading.Lock()
_current_mode = "cpu"
_orig_get_ep_list = _ie.OrtInferSession._get_ep_list


def _patched_get_ep_list(self):
    """Force the provider list RapidOCR gives to ONNX Runtime."""
    self.use_cuda = False  # attributes RapidOCR's own _verify_providers reads
    self.use_directml = False
    if _current_mode == "npu" and QNN in self.had_providers:
        backend = os.environ.get("QNN_BACKEND", "QnnHtp.dll")
        return [(QNN, {"backend_path": backend}), ("CPUExecutionProvider", {})]
    return [("CPUExecutionProvider", {"arena_extend_strategy": "kSameAsRequested"})]


_ie.OrtInferSession._get_ep_list = _patched_get_ep_list


def available_providers() -> list[str]:
    return ort.get_available_providers()


def npu_available() -> bool:
    return QNN in available_providers()


class OcrEngine:
    def __init__(self, mode: str):
        global _current_mode
        if mode == "npu" and not npu_available():
            raise RuntimeError("QNNExecutionProvider is not available in this onnxruntime build")
        with _mode_lock:
            _current_mode = mode
            self.mode = mode
            t0 = time.perf_counter()
            self._ocr = RapidOCR()
            self.load_ms = (time.perf_counter() - t0) * 1000

    def session_providers(self) -> dict[str, list[str]]:
        out = {}
        for name in ("text_det", "text_cls", "text_rec"):
            part = getattr(self._ocr, name, None)
            try:
                wrapper = getattr(part, "infer", None) or part.session  # recogniser calls it `session`
                out[name] = wrapper.session.get_providers()
            except Exception:  # internal layout differs between versions
                out[name] = ["unknown"]
        return out

    def run(self, img: Image.Image) -> tuple[list[dict[str, Any]], float]:
        arr = np.array(img.convert("RGB"))[:, :, ::-1]  # RGB -> BGR for OpenCV
        t0 = time.perf_counter()
        result, _ = self._ocr(arr)
        ms = (time.perf_counter() - t0) * 1000
        boxes = []
        for box, text, score in result or []:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            boxes.append({"text": text, "conf": float(score), "x0": min(xs), "y0": min(ys),
                          "x1": max(xs), "y1": max(ys)})
        return boxes, ms


_engines: dict[str, OcrEngine] = {}


def get_ocr(mode: str = "auto") -> OcrEngine:
    """mode: 'cpu', 'npu' or 'auto' (npu if the QNN provider exists, else cpu)."""
    if mode == "auto":
        mode = "npu" if npu_available() else "cpu"
    if mode not in _engines:
        _engines[mode] = OcrEngine(mode)
    return _engines[mode]


def system_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "onnxruntime": ort.__version__,
        "providers": available_providers(),
        "npu_provider_available": npu_available(),
        "cpu_count": os.cpu_count(),
    }
    try:
        import psutil

        proc = psutil.Process()
        info["memory_mb"] = round(proc.memory_info().rss / 1e6, 1)
        info["ram_total_mb"] = round(psutil.virtual_memory().total / 1e6)
        batt = psutil.sensors_battery()
        info["battery_percent"] = None if batt is None else round(batt.percent, 1)
        info["on_battery"] = None if batt is None else (not batt.power_plugged)
    except Exception:
        pass
    return info
