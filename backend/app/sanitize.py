"""
sanitize.py — Server-side input sanitization utilities.

All user-submitted code is passed through `sanitize_code_input()` before
being stored in the database, placed in the cache, or written to logs.

Design notes
------------
* We deliberately do NOT html.escape() here. The API speaks JSON; JSON
  serialisation already prevents HTML injection at the transport layer.
  HTML escaping is a rendering-layer concern and belongs in the frontend.
  Double-escaping on the backend would silently corrupt code that contains
  legitimate `<`, `>`, or `&` characters and would break the diff view.

* We DO strip null bytes and ANSI control sequences because these can
  poison log files or cause unexpected behaviour in terminals.
"""
from __future__ import annotations

import json
import re

# Match ANSI CSI escape sequences (colours, cursor moves, etc.)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Match raw null bytes
_NULL_RE = re.compile(r"\x00")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences so they cannot poison log output."""
    return _ANSI_RE.sub("", text)


def strip_binary_noise(text: str) -> str:
    """Remove null bytes and ANSI sequences from any user-supplied string."""
    return strip_ansi(_NULL_RE.sub("", text))


def sanitize_code_input(code: str) -> str:
    """
    Normalize and clean user-submitted source code.

    Steps:
    1. Remove null bytes (prevent log/DB injection).
    2. Remove ANSI terminal escape sequences (prevent terminal injection).

    The sanitized string is still valid source code and is safe to store,
    cache, and log. HTML escaping is intentionally left to the rendering
    layer (frontend).
    """
    return strip_binary_noise(code)


def sanitize_text_input(text: str) -> str:
    """
    Sanitize a short free-text field (e.g. action label, title, message).

    Like `sanitize_code_input` but also collapses any remaining C0/C1
    control characters that have no place in short text fields.
    """
    text = sanitize_code_input(text)
    # Strip other non-printable control chars except common whitespace
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text


def sanitize_language_hint(language: str | None) -> str | None:
    """Normalize optional language hint from API clients."""
    if language is None:
        return None
    language = sanitize_text_input(language.strip())
    if not language:
        return None
    return language[:32]


def sanitize_result_json(text: str) -> str:
    """
    Sanitize persisted analysis payloads before DB/cache storage.

    Strips null bytes and ANSI sequences, validates JSON structure, and
    returns the original string (formatting preserved) for plain-text logs.
    """
    text = strip_binary_noise(text)
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("result_json must be valid JSON") from exc
    return text
