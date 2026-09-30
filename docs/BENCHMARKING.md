# Recording the CPU vs NPU numbers

Do this on a Snapdragon X laptop. Report only what you measure.

## Setup

1. Use Windows on ARM64 Python. Install the NPU build of ONNX Runtime:
   `pip uninstall -y onnxruntime` then `pip install onnxruntime-qnn`.
2. Run `run.bat`, open the app, click the chip in the top right. "Snapdragon NPU" should say the QNN provider was found.
3. Close other apps. Use the same power mode and screen brightness for every run.

## Latency (built in)

Click **Run the CPU vs NPU test** three times. Each run does one warm-up and eight timed runs of the same frame. Copy the table into your README. The result is also saved in `benchmarks/last_run.json`.

If the NPU column shows an error, copy the message. A model that is not compiled for the NPU can fail or partly fall back to the CPU. Say so in the write-up instead of hiding it.

## Power and battery (not built into the app)

The app does not measure power. Use what Windows gives you and say which tool you used:

- Task Manager, Performance tab: watch NPU and CPU utilisation while you capture frames repeatedly.
- Battery drain: unplug, run 100 captures with the CPU engine, note the battery percentage change, recharge to the same level, repeat with the NPU engine. Use `powercfg /batteryreport` if you want a report.

Battery percentage changes are coarse. Repeat the test and report the range.

## Table for the README

| Task | Engine | Average (ms) | Fastest (ms) | Task Manager NPU use | Battery change over 100 captures |
|---|---|---|---|---|---|
| Read one code frame | CPU | | | | |
| Read one code frame | NPU | | | | |

Also record: laptop model, Windows build, Python version, onnxruntime-qnn version, and startup time and memory in low-resource mode (the drawer shows memory in use).
