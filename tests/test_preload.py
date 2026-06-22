from utils.preload import _parse_progress, _to_bytes, _is_video_unavailable


class TestParseProgress:
    def test_percent_only(self):
        assert _parse_progress("45.2%") == "45.2%"

    def test_with_size(self):
        result = _parse_progress('45.2% of 123.45MiB at 5.0MiB/s')
        assert "45.2%" in result
        assert "123.45MiB" in result
        assert "5.0MiB/s" in result

    def test_no_match(self):
        assert _parse_progress("no progress here") is None


class TestToBytes:
    def test_zero(self):
        assert _to_bytes(0) == 0

    def test_positive(self):
        assert _to_bytes(1) == 1024 * 1024
        assert _to_bytes(50) == 50 * 1024 * 1024


class TestVideoUnavailable:
    def test_sign_in_required(self):
        hint = _is_video_unavailable("sign in to confirm your age")
        assert hint is not None
        assert "youtube account" in hint.lower()

    def test_geo_blocked(self):
        hint = _is_video_unavailable("video is geo_blocked")
        assert hint is not None
        assert "blocked" in hint.lower()

    def test_available(self):
        assert _is_video_unavailable("everything is fine") is None
