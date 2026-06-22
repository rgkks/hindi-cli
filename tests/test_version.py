from version import parse_version, is_newer, __version__, __release__


class TestVersionParsing:
    def test_simple_parse(self):
        assert parse_version("1.38.4") == (1, 38, 4)
        assert parse_version("0.0.1") == (0, 0, 1)

    def test_is_newer(self):
        assert is_newer("1.38.5", "1.38.4") is True
        assert is_newer("1.38.4", "1.38.4") is False
        assert is_newer("1.38.3", "1.38.4") is False
        assert is_newer("1.10.0", "1.9.0") is True

    def test_version_consistency(self):
        parsed = parse_version(__release__)
        assert len(parsed) == 3
        assert all(isinstance(x, int) for x in parsed)
