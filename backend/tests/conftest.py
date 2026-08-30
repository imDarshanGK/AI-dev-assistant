import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Set required environment variables for tests before any app imports
os.environ.setdefault("JWT_SECRET", "test-secret-key-min-32-bytes-long-for-jwt")
