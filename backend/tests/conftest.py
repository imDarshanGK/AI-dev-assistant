import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# app.config now requires JWT_SECRET at import time. Provide a deterministic
# value for the test run so the application package can be imported during
# collection. setdefault keeps any real value supplied by the environment.
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-value-at-least-32-bytes-long")
