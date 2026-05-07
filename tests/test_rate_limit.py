import time

from github_scrape.api import RateLimitInfo, _backoff_with_jitter


class TestRateLimitInfo:
    def test_is_limited_when_zero(self) -> None:
        info = RateLimitInfo(remaining=0)
        assert info.is_limited is True

    def test_is_limited_when_positive(self) -> None:
        info = RateLimitInfo(remaining=100)
        assert info.is_limited is False

    def test_reset_datetime_with_zero_timestamp(self) -> None:
        info = RateLimitInfo(reset_timestamp=0)
        assert info.reset_datetime == "unknown"

    def test_seconds_until_reset_with_zero(self) -> None:
        info = RateLimitInfo(reset_timestamp=0)
        assert info.seconds_until_reset == 0

    def test_seconds_until_reset_future(self) -> None:
        future = int(time.time()) + 3600
        info = RateLimitInfo(reset_timestamp=future)
        assert 3500 < info.seconds_until_reset <= 3600

    def test_seconds_until_reset_past(self) -> None:
        past = int(time.time()) - 100
        info = RateLimitInfo(reset_timestamp=past)
        assert info.seconds_until_reset == 0


class TestBackoffWithJitter:
    def test_increases_with_attempts(self) -> None:
        waits = [_backoff_with_jitter(i) for i in range(4)]
        for i in range(1, len(waits)):
            assert waits[i] > waits[i - 1]

    def test_base_values_sane(self) -> None:
        wait = _backoff_with_jitter(0)
        assert 1.0 <= wait <= 1.5
        wait = _backoff_with_jitter(1)
        assert 2.0 <= wait <= 2.5
        wait = _backoff_with_jitter(2)
        assert 4.0 <= wait <= 4.5
