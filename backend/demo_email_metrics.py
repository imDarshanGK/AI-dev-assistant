import sys
import os
import time
import logging

# Ensure python can resolve app imports from backend/
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Configure logging to stdout so logs are displayed during the demo run
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

from app.config import settings
from app.services import email_service
from prometheus_client import REGISTRY

# 1. Setup settings overrides for demonstration
settings.digest_enabled = True
settings.smtp_host = "smtp.example.com"
settings.smtp_port = 2525

# Mock SMTP success implementation
class FakeSMTP:
    def __init__(self, host, port, timeout=None):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, traceback):
        return False
    def starttls(self):
        pass
    def login(self, user, password):
        pass
    def send_message(self, message):
        time.sleep(0.15)  # Simulate network latency

# Mock SMTP failure implementation
class BrokenSMTP:
    def __init__(self, host, port, timeout=None):
        pass
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, traceback):
        return False
    def starttls(self):
        pass
    def login(self, user, password):
        pass
    def send_message(self, message):
        time.sleep(0.05)  # Simulate network latency before exception
        raise Exception("SMTP Connection Failed (Simulated)")

def print_metrics():
    print("\n--- Live Prometheus Metrics (Memory Registry) ---")
    success_val = REGISTRY.get_sample_value(
        "qyverixai_email_sent_total", {"type": "digest", "status": "success"}
    ) or 0.0
    failed_val = REGISTRY.get_sample_value(
        "qyverixai_email_sent_total", {"type": "digest", "status": "failed"}
    ) or 0.0
    duration_count = REGISTRY.get_sample_value(
        "qyverixai_email_send_duration_seconds_count", {"type": "digest"}
    ) or 0.0
    duration_sum = REGISTRY.get_sample_value(
        "qyverixai_email_send_duration_seconds_sum", {"type": "digest"}
    ) or 0.0
    
    print(f"qyverixai_email_sent_total{{type=\"digest\", status=\"success\"}} = {success_val}")
    print(f"qyverixai_email_sent_total{{type=\"digest\", status=\"failed\"}}  = {failed_val}")
    print(f"qyverixai_email_send_duration_seconds_count{{type=\"digest\"}} = {duration_count}")
    print(f"qyverixai_email_send_duration_seconds_sum{{type=\"digest\"}}   = {duration_sum:.4f}s")
    if duration_count > 0:
        print(f"Average send duration: {duration_sum / duration_count:.4f}s")
    print("-------------------------------------------------\n")

def main():
    print("=== Starting QyverixAI Email Observability Video Demo ===\n")
    print_metrics()
    
    # 2. Simulate Success
    print(">>> 1. Simulating SUCCESSFUL email dispatch...")
    email_service.smtplib.SMTP = FakeSMTP
    success_stats = {
        "email": "user.success@example.com",
        "total_analyses": 5,
        "languages": ["Python", "TypeScript"],
        "avg_score": 92.5,
        "prev_avg": 85.0,
        "improvement": 8.8,
        "trend": "up",
        "top_bug": "None",
        "total_issues": 2,
        "week_start": "July 17",
        "week_end": "July 24, 2026",
    }
    
    ok = email_service.send_digest(success_stats, "token-success-demo")
    print(f"Success dispatch return value: {ok}")
    print_metrics()
    
    # 3. Simulate Failure
    print(">>> 2. Simulating FAILED email dispatch (warning log should be shown)...")
    email_service.smtplib.SMTP = BrokenSMTP
    fail_stats = {
        "email": "user.failed@example.com",
        "total_analyses": 1,
        "languages": ["Python"],
        "avg_score": 60.0,
        "prev_avg": 80.0,
        "improvement": -25.0,
        "trend": "down",
        "top_bug": "NullPointerException",
        "total_issues": 10,
        "week_start": "July 17",
        "week_end": "July 24, 2026",
    }
    
    # Run and log SMTP error
    ok = email_service.send_digest(fail_stats, "token-fail-demo")
    print(f"Failed dispatch return value: {ok}")
    print_metrics()

if __name__ == "__main__":
    main()
