#!/usr/bin/env python3
"""
demo_profiler.py — Live demonstration of the performance profiling helpers.

Shows both helpers in action:
  • @profile decorator
  • profile_block() context manager

Run with profiling OFF (default, zero overhead):
    python demo_profiler.py

Run with profiling ON (timing + peak memory logged):
    QYVERIX_PROFILE=true python demo_profiler.py
"""

from __future__ import annotations

import logging
import os
import sys
import time

# ── pretty terminal colours ────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── logging — emit DEBUG so profiler output is visible ────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    stream=sys.stdout,
)

# ── import AFTER env is in place so _ENABLED is read correctly ────────────────
from backend.app.services.profiler import profile, profile_block  # noqa: E402

# ── sample functions that mimic real analysis hotspots ────────────────────────

@profile
def ast_analyze(code: str) -> dict:
    """Simulates AST parsing — allocates a small list, sleeps briefly."""
    _ = list(range(5_000))          # ~40 KiB allocation
    time.sleep(0.001)               # 1 ms work
    return {"nodes": len(code)}


@profile
def run_bug_detection(code: str, language: str) -> list[dict]:
    """Simulates 40-pattern rule scan — heavier allocation, longer runtime."""
    _ = [{"pattern": i, "line": i * 3} for i in range(1_000)]  # ~80 KiB
    time.sleep(0.034)               # ~34 ms work
    return [{"bug": "bare-except", "line": 12}]


@profile
def run_suggestions(code: str) -> list[str]:
    """Simulates suggestion engine — medium allocation."""
    _ = list(range(10_000))         # ~80 KiB
    time.sleep(0.019)               # ~19 ms work
    return ["Add type hints", "Handle exceptions explicitly"]


@profile
def full_analysis(code: str, language: str) -> dict:
    """Wraps ast_analyze + run_bug_detection + run_suggestions."""
    info   = ast_analyze(code)
    bugs   = run_bug_detection(code, language)
    tips   = run_suggestions(code)
    time.sleep(0.03)                # extra orchestration work
    return {"info": info, "bugs": bugs, "suggestions": tips}


# ── demo ──────────────────────────────────────────────────────────────────────

SAMPLE_CODE = """\
def divide(a, b):
    try:
        return a / b
    except:          # bare-except — caught by bug detector
        pass

x = eval(input())    # eval — another pattern
"""

def main() -> None:
    enabled = os.getenv("QYVERIX_PROFILE", "false").lower() == "true"

    print()
    print(f"{BOLD}{'─'*60}{RESET}")
    print(f"{BOLD}  QyverixAI — Profiler Demo{RESET}")
    print(f"{BOLD}{'─'*60}{RESET}")
    print()

    if enabled:
        print(f"{GREEN}  QYVERIX_PROFILE=true  →  profiling ENABLED{RESET}")
        print(f"  Each function will log:  [profile] <name> | <ms> ms | peak <KiB> KiB")
    else:
        print(f"{YELLOW}  QYVERIX_PROFILE=false  →  profiling DISABLED (zero overhead){RESET}")
        print(f"  Re-run with  QYVERIX_PROFILE=true python demo_profiler.py  to see timings.")
    print()

    # ── @profile decorator examples ───────────────────────────────────────────
    print(f"{CYAN}── @profile decorator ───────────────────────────────────────{RESET}")
    print()

    result = ast_analyze(SAMPLE_CODE)
    print(f"  ast_analyze()        → {result}")

    bugs = run_bug_detection(SAMPLE_CODE, "Python")
    print(f"  run_bug_detection()  → {bugs}")

    tips = run_suggestions(SAMPLE_CODE)
    print(f"  run_suggestions()    → {tips}")
    print()

    # ── profile_block() context manager ───────────────────────────────────────
    print(f"{CYAN}── profile_block() context manager ──────────────────────────{RESET}")
    print()

    with profile_block("inline_ast_parse"):
        nodes = [ch for ch in SAMPLE_CODE if ch == "\n"]   # trivial parse
    print(f"  profile_block('inline_ast_parse') covered {len(nodes)} lines")
    print()

    # ── full_analysis (calls all three instrumented functions) ────────────────
    print(f"{CYAN}── full_analysis() — nested @profile calls ───────────────────{RESET}")
    print()
    report = full_analysis(SAMPLE_CODE, "Python")
    print(f"  full_analysis() returned {len(report)} top-level keys")
    print()

    print(f"{BOLD}{'─'*60}{RESET}")
    if enabled:
        print(f"{GREEN}  Done! See [profile] lines above for timing + memory.{RESET}")
    else:
        print(f"{YELLOW}  Done! No [profile] lines — zero overhead confirmed.{RESET}")
    print()


if __name__ == "__main__":
    main()