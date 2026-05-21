from app.services.rate_limiter import RateLimiter

def test_rate_limit_allows_initial_requests():
    limiter = RateLimiter(max_requests=3, window_seconds=60)

    assert limiter.is_allowed("user1")[0]
    assert limiter.is_allowed("user1")[0]
    assert limiter.is_allowed("user1")[0]

def test_rate_limit_blocks_excess_requests():
    limiter = RateLimiter(max_requests=2, window_seconds=60)

    limiter.is_allowed("user1")
    limiter.is_allowed("user1")

    allowed, _ = limiter.is_allowed("user1")

    assert allowed is False