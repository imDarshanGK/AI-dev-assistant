import pytest
import logging
import os
from harness.structured_logger import setup_structured_logger

@pytest.fixture
def structured_log(request):
    # Setup the structured logger using the current test's name
    test_name = request.node.name
    logger, log_path = setup_structured_logger(test_name=test_name)
    
    yield logger
    
    # Verification note to print out where artifact is saved
    print(f"\n[Artifact Saved] Structured JSON logs written to: {log_path}")

def test_application_login_scenario(structured_log):
    structured_log.info("Starting authentication flow test.")
    
    # Simulating UI/API operations
    user_url = "https://api.dev-assistant.internal/login"
    structured_log.info(f"Navigating to login endpoint: {user_url}")
    
    # Simulate a warning log entry
    structured_log.warning("API response latency exceeded 200ms threshold.")
    
    # Simulate an operational check
    assert True
    structured_log.info("Authentication flow completed successfully.")