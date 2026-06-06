import os
import shutil

ARTIFACTS = [
    ".pytest_cache",
    ".coverage",
    "htmlcov",
    ".tox",
    "logs",
    "assistant.db",
    "backend/assistant.db",
]

def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"Removed directory: {path}")
    elif os.path.isfile(path):
        os.remove(path)
        print(f"Removed file: {path}")

def cleanup():
    for root, dirs, files in os.walk("."):
        # Remove __pycache__
        if "__pycache__" in dirs:
            remove_path(os.path.join(root, "__pycache__"))

        # Remove compiled python files
        for file in files:
            if file.endswith((".pyc", ".pyo", ".pyd")):
                remove_path(os.path.join(root, file))

            if file.endswith(".log"):
                remove_path(os.path.join(root, file))

    for artifact in ARTIFACTS:
        if os.path.exists(artifact):
            remove_path(artifact)

    print("Cleanup completed successfully.")

if __name__ == "__main__":
    cleanup()