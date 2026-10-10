#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEATURE_FLAGS_PATH = PROJECT_ROOT / "feature_flags.json"
DEFAULT_ADMIN_ENV = "ADMIN_ROLE"
DEFAULT_ADMIN_TRUE = "true"


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}
    return bool(value)


def require_admin() -> None:
    """Mock RBAC check.

    Authorized if env var ADMIN_ROLE evaluates to true.
    """
    admin_role = os.environ.get(DEFAULT_ADMIN_ENV, "")
    if not _normalize_bool(admin_role):
        raise PermissionError(
            f"Unauthorized: set environment variable {DEFAULT_ADMIN_ENV}={DEFAULT_ADMIN_TRUE} to manage feature flags."
        )


def load_flags() -> Dict[str, bool]:
    if not FEATURE_FLAGS_PATH.exists():
        return {}
    raw = FEATURE_FLAGS_PATH.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("feature_flags.json must contain a JSON object at top-level.")

    normalized: Dict[str, bool] = {}
    for k, v in data.items():
        normalized[str(k)] = _normalize_bool(v)
    return normalized


def save_flags(flags: Dict[str, bool]) -> None:
    FEATURE_FLAGS_PATH.write_text(
        json.dumps({k: bool(v) for k, v in sorted(flags.items())}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def render_flags(flags: Dict[str, bool]) -> str:
    if not flags:
        return "(no feature flags set)"
    return "\n".join(
        f"{name}: {'true' if enabled else 'false'}" for name, enabled in sorted(flags.items())
    )


def cmd_list(_args: argparse.Namespace) -> int:
    flags = load_flags()
    sys.stdout.write(render_flags(flags) + "\n")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    require_admin()
    flags = load_flags()
    flags[str(args.name)] = bool(args.state)
    save_flags(flags)
    sys.stdout.write(f"Set feature flag '{args.name}' = {str(bool(args.state)).lower()}\n")
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    require_admin()
    flags = load_flags()
    name = str(args.name)
    if name in flags:
        del flags[name]
        save_flags(flags)
        sys.stdout.write(f"Unset feature flag '{name}'\n")
    else:
        sys.stdout.write(f"Feature flag '{name}' not present; nothing to unset\n")
    return 0


def parse_bool(s: str) -> bool:
    normalized = s.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "disabled"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: '{s}' (use true/false or 1/0)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage feature flags with RBAC guardrails.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Render current flags.")
    p_list.set_defaults(func=cmd_list)

    p_set = sub.add_parser("set", help="Set/update a feature flag.")
    p_set.add_argument("name", help="Feature flag name.")
    p_set.add_argument("state", type=parse_bool, help="Boolean state (true/false).")
    p_set.set_defaults(func=cmd_set)

    p_unset = sub.add_parser("unset", help="Remove/disable a feature flag.")
    p_unset.add_argument("name", help="Feature flag name.")
    p_unset.set_defaults(func=cmd_unset)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return int(args.func(args))
    except PermissionError as e:
        sys.stderr.write(str(e) + "\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

