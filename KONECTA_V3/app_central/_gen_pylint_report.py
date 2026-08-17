"""Gera pylint_results.json a partir de pylint em cada arquivo de app_central."""
import json
import re
import subprocess
import sys
from pathlib import Path

VENV_PY = Path(r"C:\KONECTA\KONECTA_V3\.venv\Scripts\python.exe")
ROOT = Path(r"C:\KONECTA\KONECTA_V3")
APP = ROOT / "app_central"
RCFILE = APP / ".pylintrc"

SCORE_RE = re.compile(r"rated at (\d+\.\d+)/10")

FILES = [
    "main.py",
    "motors/motor_konecta_v3.py",
    "motors/motor_claude_logic.py",
    "motors/motor_gemini_vision.py",
    "motors/motor_grok_context.py",
    "motors/pattern_analysis_demo.py",
    "motors/test_grok_context.py",
    "pipeline/recognizer_pipeline.py",
    "utils/metrics.py",
    "utils/video_capture.py",
]


def run_pylint(target: Path) -> tuple[dict, float | None]:
    proc = subprocess.run(
        [
            str(VENV_PY), "-m", "pylint",
            f"--rcfile={RCFILE}",
            "--output-format=text",
            str(target),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        encoding="utf-8",
    )
    out = proc.stdout + proc.stderr
    match = SCORE_RE.search(out)
    score = float(match.group(1)) if match else None
    messages = []
    counts = {"convention": 0, "refactor": 0, "warning": 0, "error": 0, "fatal": 0}
    for line in out.splitlines():
        code_type = re.search(r": (C\d+|R\d+|W\d+|E\d+|F\d+):", line)
        if code_type:
            msg_type = {"C": "convention", "R": "refactor",
                        "W": "warning", "E": "error", "F": "fatal"}[code_type.group(1)[0]]
            counts[msg_type] += 1
            messages.append(line)
    return {"messages": messages, "counts": counts}, score


def main() -> int:
    results: dict = {"overall": {}, "files": {}}
    scores = []
    for rel in FILES:
        target = APP / rel
        data, score = run_pylint(target)
        entry = {
            "score": round(score, 2) if score is not None else None,
            "message_count": len(data["messages"]),
            "by_type": data["counts"],
        }
        results["files"][rel.replace("\\", "/")] = entry
        if score is not None:
            scores.append(score)
    if scores:
        results["overall"]["mean_score"] = round(sum(scores) / len(scores), 2)
        results["overall"]["min_score"] = round(min(scores), 2)
        results["overall"]["fail_under"] = 8.0
        results["overall"]["pass"] = all(s >= 8.0 for s in scores)
    out = APP / "pylint_results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
