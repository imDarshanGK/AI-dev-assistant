"""
Unit tests for scheduler error handling.
"""

import pytest
from backend.app.services.scheduler import (
    JobFailureTracker,
    execute_job_with_error_handling,
    get_failure_tracker
)


class TestJobFailureTracker:
    """Tests for JobFailureTracker class."""
    
    def test_record_failure(self):
        tracker = JobFailureTracker(max_retries=3, failure_threshold=5)
        tracker.record_failure("test_job", Exception("Test error"))
        assert tracker.failure_counts["test_job"] == 1
        assert len(tracker.failure_logs["test_job"]) == 1
    
    def test_retry_logic(self):
        tracker = JobFailureTracker(max_retries=2, failure_threshold=3)
        assert tracker.should_retry("test_job") == True
        
        tracker.record_failure("test_job", Exception("Error 1"))
        tracker.record_failure("test_job", Exception("Error 2"))
        
        assert tracker.should_retry("test_job") == False
    
    def test_reset_after_success(self):
        tracker = JobFailureTracker(max_retries=3, failure_threshold=5)
        
        # Simulate failures
        for i in range(3):
            tracker.record_failure("test_job", Exception("Error"))
        
        assert tracker.failure_counts["test_job"] == 3
        
        # Reset after success
        tracker.reset_failure_count("test_job")
        assert tracker.failure_counts["test_job"] == 0
    
    def test_failure_summary(self):
        tracker = JobFailureTracker(max_retries=3, failure_threshold=5)
        
        tracker.record_failure("job1", Exception("Error 1"))
        tracker.record_failure("job1", Exception("Error 2"))
        tracker.record_failure("job2", Exception("Error 3"))
        
        summary = tracker.get_failure_summary()
        assert summary['total_failures'] == 3
        assert len(summary['jobs']) == 2


class TestExecuteJobWithErrorHandling:
    """Tests for job execution with error handling."""
    
    def test_successful_job(self):
        tracker = JobFailureTracker(max_retries=3, failure_threshold=5)
        
        def success():
            return "Working"
        
        result = execute_job_with_error_handling("test", success, tracker)
        assert result == "Working"
        assert tracker.failure_counts.get("test", 0) == 0
    
    def test_failing_job_retries(self):
        tracker = JobFailureTracker(max_retries=2, failure_threshold=5)
        attempts = 0
        
        def failing():
            nonlocal attempts
            attempts += 1
            raise ValueError(f"Attempt {attempts} failed")
        
        with pytest.raises(Exception):
            execute_job_with_error_handling("test", failing, tracker)
        
        # Should attempt up to 3 times (max_retries + 1)
        assert attempts == 3
        assert tracker.failure_counts.get("test", 0) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])