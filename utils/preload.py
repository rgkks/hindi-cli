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
from utils.platform import get_cache_dir, ytdl_cookie_args


_YT_ERROR_HINTS = [
    ("sign in to confirm", "This video requires a YouTube account to watch. Try a different video."),
    ("login_required", "This video requires a YouTube account to watch. Try a different video."),
    ("geo_blocked", "This video is blocked in your region. Use a VPN or try a different video."),
    ("video unavailable", "This video has been removed or is unavailable."),
    ("private video", "This video is private."),
    ("confirm your age", "This video requires age verification. Sign in to YouTube in your browser."),
    ("age-gate", "This video is age-restricted."),
]


def _is_video_unavailable(stderr: str) -> Optional[str]:
    lower = stderr.lower()
    for pattern, hint in _YT_ERROR_HINTS:
        if pattern in lower:
            return hint
    return None


PRELOAD_DIR = get_cache_dir() / "cache"

PRELOAD_FORMATS: Dict[str, str] = {
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
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
    last_fail_hint: Optional[str] = None

    def __init__(self) -> None:
        PRELOAD_DIR.mkdir(parents=True, exist_ok=True)

    def preload(self, url: str, quality: str, title: str = "",
                threshold: Optional[int] = None) -> Optional[Tuple[Path, subprocess.Popen]]:
        cfg = Config()
        if not cfg.get("preload", "enabled", default=True):
            return None
        self._maybe_cleanup()

        raw_threshold = cfg.get("preload", "threshold_mb", default=50)
        if not isinstance(raw_threshold, (int, float)) or raw_threshold <= 0:
            raw_threshold = 50
        threshold = threshold or _to_bytes(int(raw_threshold))
        fmt = PRELOAD_FORMATS.get(quality, PRELOAD_FORMATS["720p"])
        safe = re.sub(r'[^\w\- ]', '_', title)[:50] if title else "video"
        cache_stem = f"{safe}_{int(time.time())}"
        cache_path = PRELOAD_DIR / f"{cache_stem}.mp4"

        cookie_args = ytdl_cookie_args()
        proc = subprocess.Popen(
            ["yt-dlp"] + cookie_args + ["-f", fmt, "-o", str(cache_path),
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

        def _reader() -> None:
            try:
                for line in iter(proc.stderr.readline, ""):
                    with lock:
                        progress_lines.append(line.rstrip())
                    if stop_reader.is_set():
                        break
            except ValueError:
                pass
            finally:
                try:
                    proc.stderr.close()
                except OSError:
                    pass

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        status = Status("[Cache] Starting...", style="dots")
        status.start()
        start = time.time()
        last_progress = ""
        _normal_exit = False

        try:
            while True:
                ret = proc.poll()
                if ret is not None:
                    stop_reader.set()
                    time.sleep(0.05)
                    with lock:
                        stderr_tail = "\n".join(progress_lines[-5:]) if progress_lines else ""
                    try:
                        size = cache_path.stat().st_size
                    except OSError:
                        size = 0
                    if size > 0:
                        size_mb = size // 1024 // 1024
                        status.succeed(f"[Cache] Complete ({size_mb}MB)")
                        _normal_exit = True
                        return cache_path, None
                    err_msg = stderr_tail[:300] if stderr_tail else f"exit {ret}"
                    hint = _is_video_unavailable(err_msg)
                    if hint:
                        status.fail(f"[Skip] {hint}")
                        self.last_fail_hint = hint
                        Preloader._cleanup_file(cache_path)
                    else:
                        status.stop()
                        self.last_fail_hint = None
                    _normal_exit = True
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
                        _normal_exit = True
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
                        _normal_exit = True
                        return cache_path, proc
                    except OSError:
                        status.fail(f"[Cache] Timeout, no data")
                        break

                time.sleep(0.5)

            _normal_exit = True
            proc.kill()
            proc.wait()
            Preloader._cleanup_file(cache_path)
            return None

        finally:
            if not _normal_exit:
                proc.kill()
                proc.wait()
                Preloader._cleanup_file(cache_path)
            stop_reader.set()
            try:
                proc.stderr.close()
            except OSError:
                pass
            reader_thread.join(timeout=2)
            sys.stderr.write("\033[?25h")
            sys.stderr.flush()

    _cleanup_counter = 0

    def _maybe_cleanup(self) -> None:
        Preloader._cleanup_counter += 1
        if Preloader._cleanup_counter % 10 != 0:
            return
        raw_max = Config().get("preload", "max_cache_mb", default=2048)
        if not isinstance(raw_max, (int, float)) or raw_max <= 0:
            raw_max = 2048
        max_bytes = _to_bytes(int(raw_max))
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
    def cleanup_stale() -> None:
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
    def cleanup_all() -> None:
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
    def _cleanup_file(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
