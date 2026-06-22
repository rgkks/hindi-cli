import json
import tempfile
from pathlib import Path

from core.config import _deep_merge, DEFAULT_CONFIG


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"player": {"quality": "720p", "default": "mpv"}}
        override = {"player": {"quality": "1080p"}}
        result = _deep_merge(base, override)
        assert result == {"player": {"quality": "1080p", "default": "mpv"}}

    def test_new_keys_added(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_empty_override(self):
        result = _deep_merge(DEFAULT_CONFIG, {})
        assert result == DEFAULT_CONFIG

    def test_non_dict_override(self):
        base = {"player": {"quality": "720p"}}
        override = {"player": None}
        result = _deep_merge(base, override)
        assert result == {"player": None}


class TestDefaults:
    def test_default_player(self):
        assert DEFAULT_CONFIG["player"]["default"] == "mpv"
        assert DEFAULT_CONFIG["player"]["quality"] == "720p"

    def test_default_preload(self):
        assert DEFAULT_CONFIG["preload"]["enabled"] is True
        assert DEFAULT_CONFIG["preload"]["threshold_mb"] == 50
        assert DEFAULT_CONFIG["preload"]["max_cache_mb"] == 2048
