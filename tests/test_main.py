from version import parse_version, version_string, is_newer


class TestVersionHelpers:
    def test_parse_version_standard(self):
        assert parse_version("1.38.4") == (1, 38, 4)

    def test_parse_version_with_letter(self):
        result = parse_version("v2.0.0")
        assert isinstance(result, tuple)
        assert 0 in result

    def test_version_string_format(self):
        s = version_string()
        assert "hindi-cli" in s

    def test_is_newer_positive(self):
        assert is_newer("1.38.5", "1.38.4") is True

    def test_is_newer_equal(self):
        assert is_newer("1.38.4", "1.38.4") is False

    def test_is_newer_older(self):
        assert is_newer("1.38.3", "1.38.4") is False

    def test_is_newer_major(self):
        assert is_newer("2.0.0", "1.9.9") is True

    def test_is_newer_malformed(self):
        assert is_newer("abc", "1.0.0") in (True, False)
