import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from utils.platform import get_cache_dir


CACHE_DIR = get_cache_dir()


class Cache:
    def __init__(self):
        self.dir = CACHE_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self._meta = self.dir / "meta"
        self._thumbs = self.dir / "thumbs"
        self._meta.mkdir(exist_ok=True)
        self._thumbs.mkdir(exist_ok=True)

    def _key_path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()[:32]
        return self._meta / f"{h}.json"

    def get(self, key: str, max_age: int = 3600) -> Optional[Any]:
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if time.time() - data["t"] > max_age:
                path.unlink(missing_ok=True)
                return None
            return data["v"]
        except (json.JSONDecodeError, OSError, KeyError):
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        path = self._key_path(key)
        try:
            path.write_text(json.dumps({"t": time.time(), "v": value}))
        except OSError:
            pass

    def delete(self, key: str):
        self._key_path(key).unlink(missing_ok=True)

    def clear(self):
        shutil.rmtree(str(self._meta), ignore_errors=False)
        self._meta.mkdir(exist_ok=True)

    def get_thumbnail(self, video_id: str) -> Optional[Path]:
        path = self._thumbs / f"{video_id}.jpg"
        return path if path.exists() else None

    def save_thumbnail(self, video_id: str, data: bytes):
        (self._thumbs / f"{video_id}.jpg").write_bytes(data)


cache = Cache()
