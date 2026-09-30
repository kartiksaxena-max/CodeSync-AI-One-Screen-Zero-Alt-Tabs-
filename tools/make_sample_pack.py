"""Builds the sample lesson pack (silent screen-recording style video, slides,
transcript). Run once:  python tools/make_sample_pack.py

The video is synthetic: a teacher's editor where code lines appear over time.
The transcript is authored text (English + Hindi), not speech-to-text output.
Run tools/index_video.py afterwards to build code_timeline.json from the video.
Needs: Pillow, ffmpeg on PATH, and the DejaVu fonts (Linux). On Windows, edit
the three font paths below.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "lessons" / "sample-loops"
W, H = 1280, 720
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# (row number in the editor, text, second it appears)
CODE = [
    (1, "def total_marks(marks):", 6),
    (2, "    total = 0", 9),
    (3, "    for m in marks:", 13),
    (4, "        total += m", 16),
    (5, "    return total", 18),
    (7, "scores = [72, 85, 91]", 28),
    (8, "print(total_marks(scores))", 31),
    (10, "def average(marks):", 41),
    (11, "    return total_marks(marks) / len(marks)", 43),
    (13, "print(average(scores))", 48),
]
TERMINAL = [(36, "248"), (51, "82.66666666666667")]
DURATION = 60

TRANSCRIPT = [
    (0, 6, "Welcome. In this lesson we will write a function that adds up a list of marks using a for loop.",
     "स्वागत है। इस पाठ में हम एक फ़ंक्शन लिखेंगे जो for लूप की मदद से अंकों की सूची का जोड़ निकालता है।"),
    (6, 13, "First, define the function with `def`. We call it `total_marks`, and it takes one parameter, `marks`.",
     "सबसे पहले `def` से फ़ंक्शन बनाते हैं। हम इसे `total_marks` नाम देते हैं और यह एक पैरामीटर `marks` लेता है।"),
    (13, 20, "Inside, we start `total` at zero. Then a `for` loop visits every mark `m` and adds it to `total`. Finally we `return` the total.",
     "अंदर हम `total` को शून्य से शुरू करते हैं। फिर `for` लूप हर अंक `m` को देखता है और उसे `total` में जोड़ता है। अंत में हम `total` को `return` करते हैं।"),
    (20, 26, "Remember the indentation. Everything inside the function and inside the loop is pushed in by four spaces.",
     "इंडेंटेशन याद रखें। फ़ंक्शन और लूप के अंदर की हर चीज़ चार स्पेस अंदर होती है।"),
    (26, 33, "Now let's use it. We make a list called `scores` with three numbers and print the result of `total_marks`.",
     "अब इसे इस्तेमाल करते हैं। हम तीन संख्याओं की एक सूची `scores` बनाते हैं और `total_marks` का नतीजा प्रिंट करते हैं।"),
    (33, 40, "Run it and you should see 248. That is 72 plus 85 plus 91.",
     "इसे चलाएँ तो आपको 248 दिखना चाहिए। यानी 72 जमा 85 जमा 91।"),
    (40, 47, "Next, `average`. It reuses `total_marks` and divides by `len` of the list, which counts the items.",
     "अब `average`। यह `total_marks` का दोबारा इस्तेमाल करता है और सूची की `len` से भाग देता है, जो आइटम गिनती है।"),
    (47, 54, "Print `average` of `scores`. You get 82.666, a float, because division in Python always gives a float.",
     "`scores` का `average` प्रिंट करें। आपको 82.666 मिलता है, एक फ़्लोट, क्योंकि पायथन में भाग हमेशा फ़्लोट देता है।"),
    (54, 60, "Checkpoint: write a function `count_above` that counts how many marks are above a limit. Try it yourself before moving on.",
     "चेकपॉइंट: एक फ़ंक्शन `count_above` लिखें जो गिनता है कि कितने अंक किसी सीमा से ऊपर हैं। आगे बढ़ने से पहले खुद कोशिश करें।"),
]

SLIDES = [
    (0, "Loops and functions", ["Goal: add up a list of marks", "Tools: def, for, return"]),
    (6, "Anatomy of a function", ["def name(parameter):", "    indented body", "    return result"]),
    (54, "Checkpoint: count_above", ["Write count_above(marks, limit)", "Count marks greater than limit"]),
]


def font(path, size):
    return ImageFont.truetype(path, size)


def draw_state(t: float) -> Image.Image:
    if t < 6:
        img = Image.new("RGB", (W, H), "#1b2233")
        d = ImageDraw.Draw(img)
        d.text((90, 250), "Lesson 1", font=font(SANS_B, 54), fill="#ffe066")
        d.text((90, 330), "Loops and functions in Python", font=font(SANS, 40), fill="#e6ecff")
        return img
    img = Image.new("RGB", (W, H), "#1b2233")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 54], fill="#121826")
    d.text((24, 12), "lesson1.py  -  teacher screen", font=font(SANS, 24), fill="#9fb0d0")
    d.rectangle([0, 54, 84, 520], fill="#171e2e")
    mono, pitch = font(MONO, 28), 34
    for row, text, at in CODE:
        if t >= at:
            y = 70 + (row - 1) * pitch
            d.text((20, y), f"{row}", font=mono, fill="#5d6b8a")
            d.text((110, y), text, font=mono, fill="#e6ecff")
    d.rectangle([0, 540, W, H], fill="#0f1420")
    d.text((24, 552), "terminal", font=font(SANS, 20), fill="#6f7fa3")
    y = 590
    if t >= 34:
        d.text((24, y), "$ python lesson1.py", font=mono, fill="#9fb0d0")
        y += pitch
    for at, out in TERMINAL:
        if t >= at:
            d.text((24, y), out, font=mono, fill="#7ddca4")
            y += pitch
    return img


def make_video():
    frames = PACK / "_frames"
    frames.mkdir(exist_ok=True)
    marks = sorted({0, DURATION, 6, 34} | {a for _, _, a in CODE} | {a for a, _ in TERMINAL})
    lines = []
    for i, start in enumerate(marks[:-1]):
        p = frames / f"s{i:02d}.png"
        draw_state(start + 0.01).save(p)
        lines.append(f"file '{p.name}'\nduration {marks[i + 1] - start}")
    lines.append(f"file 's{len(marks) - 2:02d}.png'")
    (frames / "list.txt").write_text("\n".join(lines))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(frames / "list.txt"),
         "-vf", "fps=10,format=yuv420p", "-c:v", "libx264", "-movflags", "+faststart", str(PACK / "video.mp4")],
        check=True)
    draw_state(52).crop((0, 54, W, 520)).save(PACK / "bench_frame.png")
    for f in frames.iterdir():
        f.unlink()
    frames.rmdir()


def make_slides():
    (PACK / "slides").mkdir(exist_ok=True)
    out = []
    for i, (t, title, bullets) in enumerate(SLIDES, 1):
        img = Image.new("RGB", (W, H), "#f6f7f9")
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 24, H], fill="#2f55d4")
        d.text((90, 90), title, font=font(SANS_B, 56), fill="#10182b")
        y = 250
        for b in bullets:
            f = font(MONO, 40) if b.startswith(("def", "    ")) else font(SANS, 40)
            d.text((90, y), b, font=f, fill="#2b3450")
            y += 70
        name = f"slides/slide{i}.png"
        img.save(PACK / name)
        out.append({"img": name, "time": t, "title": title,
                    "text": title + ". " + " ".join(b.strip() for b in bullets)})
    return out


def main():
    make_video()
    lesson = {
        "id": "sample-loops",
        "title": "Python: loops and functions",
        "language": "python",
        "video": "video.mp4",
        "duration": DURATION,
        "transcript_source": "authored sample text (not speech-to-text output); video is silent",
        "transcript": [{"start": a, "end": b, "text": en, "text_hi": hi} for a, b, en, hi in TRANSCRIPT],
        "chapters": [
            {"time": 0, "title": "Intro"}, {"time": 6, "title": "Defining total_marks"},
            {"time": 26, "title": "Calling and running it"}, {"time": 40, "title": "The average function"},
            {"time": 54, "title": "Checkpoint"},
        ],
        "slides": make_slides(),
        # fraction of the frame that holds the teacher's code: x0, y0, x1, y1
        "capture_crop": [0.0, 0.08, 1.0, 0.72],
        "checkpoints": [{
            "time": 54,
            "title": "Write count_above",
            "prompt": "Write count_above(marks, limit) so it returns how many marks are greater than limit.",
            "starter": "def count_above(marks, limit):\n    # your code here\n    pass\n",
            "tests": "print(count_above([72, 85, 91], 80))\nprint(count_above([10, 20], 50))",
            "expected": "2\n0",
            "hints": [
                {"level": 1, "text": "You need something that starts at zero and grows while you loop over the marks. Which variable in total_marks does that?", "jump": 13},
                {"level": 2, "text": "Add an if inside the for loop: only when m > limit should the counter go up by one.", "jump": 13},
                {"level": 3, "text": "def count_above(marks, limit):\n    count = 0\n    for m in marks:\n        if m > limit:\n            count += 1\n    return count\n", "jump": None},
            ],
        }],
    }
    (PACK / "lesson.json").write_text(json.dumps(lesson, indent=2, ensure_ascii=False))
    print("sample pack written to", PACK)


if __name__ == "__main__":
    sys.exit(main())
