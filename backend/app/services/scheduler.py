"""
Scheduler service for handling background jobs with improved error handling.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class JobFailure:
    """Record of a job failure."""
    timestamp: str
    error_message: str
    retry_count: int
    job_name: str


class JobFailureTracker:
    """
    Tracks job failures, manages retries, and sends alerts when thresholds are exceeded.
    """
    
    def __init__(self, max_retries: int = 3, failure_threshold: int = 5):
        """
        Initialize the failure tracker.
        
        Args:
            max_retries: Maximum number of retry attempts before giving up
            failure_threshold: Number of failures before sending an alert
        """
        self.max_retries = max_retries
        self.failure_threshold = failure_threshold
        self.failure_counts: Dict[str, int] = {}
        self.failure_logs: Dict[str, List[JobFailure]] = {}
        self.alert_sent_for_job: Dict[str, bool] = {}
    
    def record_failure(self, job_name: str, error: Exception) -> None:
        """
        Record a job failure with timestamp and error details.
        
        Args:
            job_name: Name of the failed job
            error: The exception that occurred
        """
        # Initialize tracking for this job if not exists
        if job_name not in self.failure_counts:
            self.failure_counts[job_name] = 0
            self.failure_logs[job_name] = []
            self.alert_sent_for_job[job_name] = False
        
        # Increment failure count
        self.failure_counts[job_name] += 1
        
        # Log the failure
        failure = JobFailure(
            timestamp=datetime.now().isoformat(),
            error_message=str(error),
            retry_count=self.failure_counts[job_name],
            job_name=job_name
        )
        self.failure_logs[job_name].append(failure)
        
        # Log to console
        logger.error(f"Job '{job_name}' failed (attempt {self.failure_counts[job_name]}): {error}")
        
        # Check if threshold exceeded
        if self.failure_counts[job_name] >= self.failure_threshold:
            self._send_alert(job_name)
    
    def _send_alert(self, job_name: str) -> None:
        """
        Send an alert when failure threshold is exceeded.
        
        Args:
            job_name: Name of the failing job
        """
        if self.alert_sent_for_job.get(job_name, False):
            return
        
        alert_message = (
            f"\n{'='*60}\n"
            f"⚠️ ALERT: Job '{job_name}' has exceeded failure threshold!\n"
            f"Total failures: {self.failure_counts[job_name]}\n"
            f"Threshold: {self.failure_threshold}\n"
            f"Last error: {self.failure_logs[job_name][-1].error_message if self.failure_logs[job_name] else 'Unknown'}\n"
            f"Action required: Investigate the job failures immediately.\n"
            f"{'='*60}"
        )
        logger.critical(alert_message)
        
        # Mark alert as sent
        self.alert_sent_for_job[job_name] = True
        # TODO: Integrate with email/webhook notification system here
    
    def reset_failure_count(self, job_name: str) -> None:
        """
        Reset failure count after a successful execution.
        
        Args:
            job_name: Name of the job that succeeded
        """
        if job_name in self.failure_counts:
            self.failure_counts[job_name] = 0
            self.alert_sent_for_job[job_name] = False
            logger.info(f"Failure count reset for job '{job_name}' after successful execution")
    
    def should_retry(self, job_name: str) -> bool:
        """
        Check if a job should be retried.
        
        Args:
            job_name: Name of the job to check
        
        Returns:
            True if retry is allowed, False otherwise
        """
        current_retries = self.failure_counts.get(job_name, 0)
        return current_retries < self.max_retries
    
    def get_failure_summary(self, job_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a summary of failures for a job or all jobs.
        
        Args:
            job_name: Specific job name (optional)
        
        Returns:
            Dictionary with failure summary
        """
        if job_name:
            return {
                'job_name': job_name,
                'failure_count': self.failure_counts.get(job_name, 0),
                'failures': [
                    {
                        'timestamp': f.timestamp,
                        'error': f.error_message,
                        'retry_count': f.retry_count
                    }
                    for f in self.failure_logs.get(job_name, [])
                ]
            }
        else:
            return {
                'jobs': [
                    {
                        'job_name': name,
                        'failure_count': count,
                        'last_failure': self.failure_logs[name][-1].timestamp if self.failure_logs.get(name) else None
                    }
                    for name, count in self.failure_counts.items()
                ],
                'total_failures': sum(self.failure_counts.values())
            }


def execute_job_with_error_handling(
    job_name: str,
    job_func: Callable,
    tracker: JobFailureTracker,
    *args,
    **kwargs
) -> Any:
    """
    Execute a job with automatic retry and error handling.
    
    Args:
        job_name: Name of the job
        job_func: Function to execute
        tracker: JobFailureTracker instance
        *args: Positional arguments for job_func
        **kwargs: Keyword arguments for job_func
    
    Returns:
        Result of job_func if successful
    
    Raises:
        Exception: If job fails after max retries
    """
    max_attempts = tracker.max_retries + 1
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Executing job '{job_name}' (attempt {attempt}/{max_attempts})")
            result = job_func(*args, **kwargs)
            tracker.reset_failure_count(job_name)
            logger.info(f"Job '{job_name}' completed successfully")
            return result
        except Exception as e:
            tracker.record_failure(job_name, e)
            
            if not tracker.should_retry(job_name):
                logger.error(f"Job '{job_name}' exceeded max retries. Giving up.")
                raise
            else:
                logger.warning(f"Job '{job_name}' failed. Will retry. Error: {e}")
    
    raise RuntimeError(f"Job '{job_name}' failed after {max_attempts} attempts")


# Global tracker instance
_failure_tracker = JobFailureTracker()


def get_failure_tracker() -> JobFailureTracker:
    """Get the global failure tracker instance."""
    return _failure_tracker


# Example usage:
if __name__ == "__main__":
    # Test the scheduler error handling
    def failing_job():
        raise ValueError("Test error - job failed")
    
    def successful_job():
        return "Success!"
    
    # Test successful job
    result = execute_job_with_error_handling(
        "test_success",
        successful_job,
        _failure_tracker
    )
    print(f"Successful job result: {result}")
    
    # Test failing job (will retry)
    try:
        execute_job_with_error_handling(
            "test_failure",
            failing_job,
            _failure_tracker
        )
    except Exception as e:
        print(f"Job failed as expected: {e}")
    
    # Print failure summary
    print("\nFailure Summary:")
    print(_failure_tracker.get_failure_summary())