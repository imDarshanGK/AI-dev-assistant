"""Shared Pydantic field validators for user-supplied request data."""

from __future__ import annotations
from typing import Optional, List, Dict
from .sanitize import (
    sanitize_code_input,
    sanitize_language_hint,
    sanitize_result_json,
    sanitize_text_input,
)

validate_stored_action = sanitize_text_input
validate_stored_code = sanitize_code_input
validate_stored_result_json = sanitize_result_json
validate_language_hint = sanitize_language_hint


def validate_chat_history(items: List[str]) -> List[str]:
    return [sanitize_text_input(item) for item in items]
