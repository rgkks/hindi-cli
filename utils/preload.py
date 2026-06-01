import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from core.config import Config
from ui.status import Status
from utils.logger import log
from utils.platform import get_cache_dir


PRELOAD_DIR = get_cache_dir() / "cache"

PRELOAD_FORMATS: Dict[str, str] = {
    "2160p": "best[height<=2160]",
    "1440p": "best[height<=1440]",
    "1080p": "best[height<=1080]",
    "720p": "best[height<=720]",
    "480p": "best[height<=480]",
    "360p": "best[height<=360]",
    "audio": "bestaudio/best",
}


def _to_bytes(mb: int) -> int:
    return mb * 1024 * 1024


def _parse_progress(line: str) -> Optional[str]:
    m = re.search(r'(\d+\.?\d*)%', line)
    if not m:
        return None
    pct = m.group(1)
    rest = line[m.end():]
    m2 = re.search(r'of\s+~?([\d.]+)\s*(MiB|GiB|KiB)', rest)
    size_str = f" {m2.group(1)}{m2.group(2)}" if m2 else ""
    m3 = re.search(r'at\s+([\d.]+(?:MiB|GiB|KiB)/s)', rest)
    speed_str = f" {m3.group(1)}" if m3 else ""
    return f"{pct}%{size_str}{speed_str}"


class Preloader:
    def __init__(self):
        PRELOAD_DIR.mkdir(parents=True, exist_ok=True)

    def preload(self, url: str, quality: str, title: str = "",
                threshold: Optional[int] = None) -> Optional[Tuple[Path, subprocess.Popen]]:
        cfg = Config()
        if not cfg.get("preload", "enabled", default=True):
            return None
        self._maybe_cleanup()

        threshold = threshold or _to_bytes(cfg.get("preload", "threshold_mb", default=50))
        fmt = PRELOAD_FORMATS.get(quality, PRELOAD_FORMATS["720p"])
        safe = re.sub(r'[^\w\- ]', '_', title)[:50] if title else "video"
        cache_stem = f"{safe}_{int(time.time())}"
        cache_path = PRELOAD_DIR / f"{cache_stem}.mp4"

        proc = subprocess.Popen(
            ["yt-dlp", "-f", fmt, "-o", str(cache_path),
             "--no-warnings", "--no-mtime", "--no-part",
             "--progress", "--newline",
             url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )

        progress_lines: list = []
        lock = threading.Lock()
        stop_reader = threading.Event()

        def _reader():
            for line in proc.stderr:
                with lock:
                    progress_lines.append(line.rstrip())
                if stop_reader.is_set():
                    break

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        status = Status("[Cache] Starting...", style="dots")
        status.start()
        start = time.time()
        last_progress = ""

        try:
            while True:
                ret = proc.poll()
                if ret is not None:
                    stop_reader.set()
                    try:
                        size = cache_path.stat().st_size
                    except OSError:
                        size = 0
                    if size > 0:
                        size_mb = size // 1024 // 1024
                        status.succeed(f"[Cache] Complete ({size_mb}MB)")
                        return cache_path, None
                    status.fail(f"[Cache] Failed (exit {ret})")
                    Preloader._cleanup_file(cache_path)
                    return None

                elapsed = int(time.time() - start)

                with lock:
                    while progress_lines:
                        line = progress_lines.pop(0)
                        parsed = _parse_progress(line)
                        if parsed:
                            last_progress = parsed

                try:
                    size = cache_path.stat().st_size
                except OSError:
                    size = 0

                if size > 0:
                    size_mb = size // 1024 // 1024
                    pct = min(size / threshold, 1.0)
                    status.update(message=f"[Cache] {size_mb}MB", progress=pct)

                    if size >= threshold:
                        status.succeed(f"[Cache] Buffer ready: {size_mb}MB")
                        return cache_path, proc
                elif last_progress:
                    status.update(message="[Cache] Downloading...")
                else:
                    status.update(message="[Cache] Resolving formats...")

                if elapsed > 90:
                    try:
                        size = cache_path.stat().st_size
                        size_mb = size // 1024 // 1024
                        status.succeed(f"[Cache] Partial ({size_mb}MB), starting playback")
                        return cache_path, proc
                    except OSError:
                        status.fail(f"[Cache] Timeout, no data")
                        break

                time.sleep(0.5)

            proc.kill()
            proc.wait()
            Preloader._cleanup_file(cache_path)
            return None

        finally:
            stop_reader.set()
            reader_thread.join(timeout=2)
            sys.stderr.write("\033[?25h")
            sys.stderr.flush()

    def _maybe_cleanup(self):
        max_bytes = _to_bytes(Config().get("preload", "max_cache_mb", default=2048))
        try:
            files = [f for f in PRELOAD_DIR.iterdir() if f.is_file()]
            total = sum(f.stat().st_size for f in files)
            if total < max_bytes:
                return
            files.sort(key=lambda f: f.stat().st_mtime)
            for f in files:
                if total < max_bytes:
                    break
                total -= f.stat().st_size
                f.unlink(missing_ok=True)
                log.info(f"Cache evicted: {f.name}")
        except Exception as e:
            log.warning(f"Cache cleanup error: {e}")

    @staticmethod
    def cleanup_stale():
        PRELOAD_DIR.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in PRELOAD_DIR.iterdir():
            if f.is_file():
                try:
                    age = time.time() - f.stat().st_mtime
                    if age > 86400:
                        f.unlink(missing_ok=True)
                        count += 1
                except Exception:
                    pass
        if count:
            log.info(f"Cleaned {count} stale cache files")

    @staticmethod
    def cleanup_all():
        count = 0
        try:
            for f in PRELOAD_DIR.iterdir():
                if f.is_file():
                    f.unlink(missing_ok=True)
                    count += 1
        except Exception:
            pass
        if count:
            log.info(f"Cleaned {count} cache files on exit")

    @staticmethod
    def _cleanup_file(path: Path):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
