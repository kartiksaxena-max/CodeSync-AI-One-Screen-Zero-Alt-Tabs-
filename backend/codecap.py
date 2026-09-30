"""Code-from-video capture: OCR boxes -> clean code lines.

Steps: group boxes into lines, drop an editor line-number gutter, rebuild
indentation from x-positions, restore blank lines from vertical gaps, and fix
likely OCR typos against a vocabulary (Python keywords/builtins plus the
identifiers the teacher mentions in the transcript and slides).
"""
from __future__ import annotations

import builtins
import difflib
import keyword
import re
import statistics
from typing import Any

BASE_VOCAB = set(keyword.kwlist) | {n for n in dir(builtins) if not n.startswith("_")}
IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
CONFUSIONS = str.maketrans({"0": "o", "1": "l", "5": "s", "|": "l"})
FULLWIDTH = str.maketrans({"，": ",", "（": "(", "）": ")", "：": ":", "；": ";", "［": "[", "］": "]", "＝": "=", "＋": "+", "“": '"', "”": '"', "‘": "'", "’": "'"})


def build_vocab(*texts: str) -> set[str]:
    vocab = set(BASE_VOCAB)
    for t in texts:
        vocab.update(w for w in IDENT.findall(t) if len(w) > 1)
    return vocab


def _group_lines(boxes: list[dict]) -> list[list[dict]]:
    if not boxes:
        return []
    heights = [b["y1"] - b["y0"] for b in boxes]
    tol = 0.6 * statistics.median(heights)
    lines: list[list[dict]] = []
    for b in sorted(boxes, key=lambda b: (b["y0"] + b["y1"]) / 2):
        yc = (b["y0"] + b["y1"]) / 2
        if lines and abs(yc - lines[-1][0]["_yc"]) < tol:
            lines[-1].append(b)
        else:
            b["_yc"] = yc
            lines.append([b])
    return [sorted(l, key=lambda b: b["x0"]) for l in lines]


def _drop_gutter(boxes: list[dict]) -> list[dict]:
    """Remove the editor's line-number column: digit-only boxes left of the code."""
    def digits_only(b):
        return re.fullmatch(r"[\d\s.:]{1,12}", b["text"].strip()) is not None

    code = [b for b in boxes if not digits_only(b)]
    if not code:
        return boxes
    code_left = min(b["x0"] for b in code)
    # entirely left of every code box = gutter (a code line "5" starts at the code column, not left of it)
    dropped = [b for b in boxes if digits_only(b) and b["x1"] < code_left]
    return [b for b in boxes if b not in dropped]


def _drop_merged_numbers(lines: list[list[dict]]) -> list[list[dict]]:
    """Gutter numbers glued to the code text: '12  def f():'."""
    merged = sum(1 for l in lines if re.match(r"^\d{1,3}\s+\S", l[0]["text"]))
    if lines and merged >= 0.6 * len(lines):
        for l in lines:
            l[0] = dict(l[0], text=re.sub(r"^\d{1,3}\s+", "", l[0]["text"]))
    return lines


def _fix_token(tok: str, vocab: set[str]) -> str:
    if tok in vocab or len(tok) < 3 or tok.isdigit():
        return tok
    variant = tok.translate(CONFUSIONS)
    if variant in vocab:
        return variant
    m = difflib.get_close_matches(tok, vocab, n=1, cutoff=0.82)
    return m[0] if m else tok


PAIR = re.compile(r"(?=\b([A-Za-z_]\w*) ([A-Za-z_]\w*)\b)")


def fix_typos(line: str, vocab: set[str]) -> tuple[str, list[tuple[str, str]]]:
    fixes: list[tuple[str, str]] = []
    # OCR often drops underscores: "total marks" -> total_marks when that is a known name.
    # Lookahead matching so overlapping pairs ("def total marks") are all considered.
    for m in reversed(list(PAIR.finditer(line))):
        a, b = m.group(1), m.group(2)
        if f"{a}_{b}" in vocab and not keyword.iskeyword(a) and not keyword.iskeyword(b):
            start = m.start()
            fixes.append((f"{a} {b}", f"{a}_{b}"))
            line = line[:start] + f"{a}_{b}" + line[start + len(a) + 1 + len(b):]
    line = line.translate(FULLWIDTH)
    line = re.sub(r"\s+([:,)\]])", r"\1", line)
    line = re.sub(r"([(\[])\s+", r"\1", line)

    def repl(m):
        new = _fix_token(m.group(0), vocab)
        if new != m.group(0):
            fixes.append((m.group(0), new))
        return new

    return IDENT.sub(repl, line), fixes


def _snap_unit(indents: list[int]) -> int:
    nz = [i for i in indents if i > 0]
    if not nz:
        return 4
    best, best_err = 4, 10**9
    for unit in (4, 2, 8):
        err = sum(min(i % unit, unit - i % unit) for i in nz)
        if err < best_err:
            best, best_err = unit, err
    return best


def boxes_to_code(boxes: list[dict], vocab: set[str]) -> dict[str, Any]:
    boxes = [dict(b) for b in boxes if b["text"].strip()]
    lines = _drop_merged_numbers(_group_lines(_drop_gutter(boxes)))
    if not lines:
        return {"lines": [], "code": "", "engine_note": "no text found"}

    char_ws = [(b["x1"] - b["x0"]) / max(len(b["text"]), 1) for l in lines for b in l]
    char_w = statistics.median(char_ws) or 1.0
    left = min(l[0]["x0"] for l in lines)
    raw_indents = [round((l[0]["x0"] - left) / char_w) for l in lines]
    unit = _snap_unit(raw_indents)

    ycs = [(l[0]["y0"] + l[0]["y1"]) / 2 for l in lines]
    gaps = [b - a for a, b in zip(ycs, ycs[1:])]
    pitch = statistics.median(gaps) if gaps else 0

    out, code_lines = [], []
    for i, l in enumerate(lines):
        if i > 0 and pitch:
            blanks = round(gaps[i - 1] / pitch) - 1
            for _ in range(max(0, min(blanks, 3))):
                code_lines.append("")
                out.append({"text": "", "indent": 0, "conf": 1.0, "fixes": [], "blank": True})
        text = ""
        prev_x1 = None
        for b in l:
            if prev_x1 is not None:
                text += " " * max(1, round((b["x0"] - prev_x1) / char_w))
            text += b["text"]
            prev_x1 = b["x1"]
        text, fixes = fix_typos(text.strip(), vocab)
        indent = round(raw_indents[i] / unit) * unit
        full = " " * indent + text
        conf = min(b["conf"] for b in l)
        code_lines.append(full)
        out.append({"text": full, "indent": indent, "conf": round(conf, 3), "fixes": fixes, "blank": False})
    return {"lines": out, "code": "\n".join(code_lines), "indent_unit": unit}


def looks_like_code(text: str) -> bool:
    """Skip title cards and captions: code has operators, brackets or a keyword first."""
    t = text.strip()
    if len(t) < 2:
        return False
    first = t.split()[0] if t.split() else ""
    return bool(re.search(r"[=()\[\]{}:+\-*/%<>]", t)) or keyword.iskeyword(first)
