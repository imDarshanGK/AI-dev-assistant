from pathlib import Path
import shutil
import time

THRESHOLD_DAYS = 7
CURRENT_TIME = time.time()


def is_stale(path: Path) -> bool:
    age_days = (CURRENT_TIME - path.stat().st_mtime) / 86400
    return age_days > THRESHOLD_DAYS


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent

    artifact_names = {
        ".pytest_cache",
        "__pycache__",
        "assistant.db",
    }

    removed = []

    for path in project_root.rglob("*"):
        if path.name in artifact_names and is_stale(path):
            remove_path(path)
            removed.append(str(path))

    print(f"Removed {len(removed)} stale artifacts")

    for item in removed:
        print(f"- {item}")


if __name__ == "__main__":
    main()