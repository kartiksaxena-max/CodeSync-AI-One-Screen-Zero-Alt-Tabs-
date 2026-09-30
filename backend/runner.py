"""Run student code locally and explain errors in plain language.

The code runs as a normal subprocess of the student's own machine with a time
limit. This is a local learning tool, not a hardened sandbox: do not expose the
server to other people's networks.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_S = 5
MAX_OUT = 8000

EXPLAIN = {
    "IndentationError": ("Python uses indentation to know which lines belong together. Line up the lines inside the function and the loop.", "indentation four spaces"),
    "TabError": ("Tabs and spaces are mixed. Use four spaces everywhere.", "indentation four spaces"),
    "SyntaxError": ("Python could not read a line. Check for a missing colon after def or for, a missing bracket, or a missing quote.", "define function def parameter"),
    "NameError": ("You used a name that has not been defined yet. Check the spelling, and make sure it is created before this line runs.", None),
    "TypeError": ("An operation got the wrong kind of value, for example adding a number to text, or calling a function with the wrong number of arguments.", "function parameter list numbers"),
    "ZeroDivisionError": ("The code divided by zero. In average, that happens when the list is empty.", "average divide len"),
    "IndexError": ("The code asked for a list position that does not exist.", "list items len"),
    "ValueError": ("A function got a value of the right type but with content it cannot use.", None),
    "AttributeError": ("The value has no such method or attribute. Check the spelling and the type of the value.", None),
}


def run_code(code: str, extra: str = "") -> dict:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "main.py"
        path.write_text(code + ("\n" + extra if extra else "") + "\n", encoding="utf-8")
        try:
            p = subprocess.run([sys.executable, "-I", str(path)], capture_output=True, text=True,
                               timeout=TIMEOUT_S, cwd=d)
            return {"stdout": p.stdout[:MAX_OUT], "stderr": p.stderr[:MAX_OUT], "returncode": p.returncode,
                    "timed_out": False}
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": f"Stopped after {TIMEOUT_S} seconds. Is there a loop that never ends?",
                    "returncode": -1, "timed_out": True}


def explain(stderr: str) -> dict | None:
    lines = [l for l in stderr.strip().splitlines() if l.strip()]
    if not lines:
        return None
    m = re.match(r"^(\w+(?:Error|Exception))(?::\s*(.*))?$", lines[-1])
    if not m:
        return {"type": "Error", "message": lines[-1], "explanation": "Read the last line of the message: it says what went wrong.", "query": None}
    etype, msg = m.group(1), m.group(2) or ""
    text, query = EXPLAIN.get(etype, ("Read the last line of the message: it says what went wrong.", None))
    if etype == "NameError":
        name = re.search(r"name '(\w+)'", msg)
        query = name.group(1) if name else None
    return {"type": etype, "message": msg, "explanation": text, "query": query}


def check(code: str, checkpoint: dict) -> dict:
    res = run_code(code, checkpoint["tests"])
    got = res["stdout"].strip().replace("\r\n", "\n")
    res["passed"] = res["returncode"] == 0 and got == checkpoint["expected"].strip()
    res["expected"], res["got"] = checkpoint["expected"], got
    return res
