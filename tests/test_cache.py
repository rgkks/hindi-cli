import tempfile
from pathlib import Path

from utils.cache import Cache


class TestCache:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = Cache()
        self.cache.dir = self.tmp
        self.cache._meta = self.tmp / "meta"
        self.cache._meta.mkdir(exist_ok=True)

    def test_set_and_get(self):
        self.cache.set("key1", {"data": 123}, ttl=3600)
        result = self.cache.get("key1", max_age=3600)
        assert result == {"data": 123}

    def test_get_expired(self):
        self.cache.set("key2", "value", ttl=0)
        result = self.cache.get("key2", max_age=0)
        assert result is None

    def test_get_nonexistent(self):
        assert self.cache.get("nonexistent") is None

    def test_delete(self):
        self.cache.set("key3", "value")
        self.cache.delete("key3")
        assert self.cache.get("key3") is None
