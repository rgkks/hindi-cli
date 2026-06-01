import json
from pathlib import Path
from typing import Any

from utils.platform import get_app_dir, get_cache_dir


CONFIG_DIR = Path.home() / ".config" / "hindi-cli"
CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_DIR = get_app_dir()
CACHE_DIR = get_cache_dir()


DEFAULT_CONFIG = {
    "player": {
        "default": "mpv",
        "mpv_args": [
            "--cache-secs=600",
            "--demuxer-max-bytes=512M",
            "--demuxer-readahead-secs=120",
            "--stream-buffer-size=128M",
            "--cache-pause-wait=10",
        ],
        "vlc_args": [],
        "quality": "720p",
    },
    "ui": {
        "theme": "dark",
        "icons": False,
        "preview": False,
        "thumbnails": False,
    },
    "behavior": {
        "autoplay_next": True,
        "skip_intro": False,
        "skip_outro": False,
        "history_size": 500,
    },
    "preload": {
        "enabled": True,
        "threshold_mb": 50,
        "max_cache_mb": 2048,
    },
    "plugins_dir": str(CONFIG_DIR / "plugins"),
}


class Config:
    _instance = None
    _merged: dict = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._loaded = True
        self.data: dict = {}
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        if CONFIG_PATH.exists():
            try:
                self.data = json.loads(CONFIG_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                self.data = {}
        else:
            self._save()

    def _save(self):
        self._merged = {**DEFAULT_CONFIG, **self.data}
        CONFIG_PATH.write_text(json.dumps(self._merged, indent=2))

    def get(self, *keys: str, default: Any = None) -> Any:
        if not self._merged:
            self._merged = {**DEFAULT_CONFIG, **self.data}
        current = self._merged
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current

    def set(self, value: Any, *keys: str):
        current = self.data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
        self._merged = {}
        self._save()

    @property
    def player_name(self) -> str:
        return self.get("player", "default") or "mpv"

    @property
    def quality(self) -> str:
        return self.get("player", "quality") or "720p"

    @property
    def use_icons(self) -> bool:
        return self.get("ui", "icons") or False


config = Config()
