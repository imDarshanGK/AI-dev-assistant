import json
import logging
import os
import time
from datetime import datetime

class JsonStructuredFormatter(logging.Formatter):
    def __init__(self, test_name="N/A", url="N/A", browser="Python-Requests/Playwright"):
        super().__init__()
        self.test_name = test_name
        self.url = url
        self.browser = browser

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "testName": self.test_name,
            "url": self.url,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "file": f"{record.filename}:{record.lineno}",
            "browser": self.browser
        }
        return json.dumps(log_entry)

def setup_structured_logger(test_name, output_dir="test_artifacts"):
    os.makedirs(output_dir, exist_ok=True)
    
    logger = logging.getLogger(test_name)
    logger.setLevel(logging.INFO)
    # Prevent duplicate handlers if fixture re-runs
    if logger.hasHandlers():
        logger.handlers.clear()

    log_file_path = os.path.join(output_dir, f"structured_logs_{int(time.time())}.json")
    
    file_handler = logging.FileHandler(log_file_path)
    formatter = JsonStructuredFormatter(test_name=test_name)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    return logger, log_file_path