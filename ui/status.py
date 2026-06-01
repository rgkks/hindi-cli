import sys
import threading
import time
from typing import Optional


_STYLES = {
    "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
    "spin": ["|", "/", "-", "\\"],
    "line": ["╺", "╸", "╺", "╸", "━"],
    "bounce": ["⠁", "⠂", "⠄", "⡀", "⡄", "⡆", "⡇", "⣧", "⣇", "⣇", "⡇", "⡆", "⡄", "⡀", "⠄", "⠂", "⠁"],
}


def _is_interactive() -> bool:
    return sys.stderr.isatty()


def _bar(progress: float, width: int = 16) -> str:
    filled = int(width * progress)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


class Status:
    def __init__(self, message: str = "", style: str = "dots"):
        self._message = message
        self._chars = _STYLES.get(style, _STYLES["dots"])
        self._stream = sys.stderr
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._progress: Optional[float] = None
        self._finalized = False
        self._interactive = _is_interactive()

    def start(self, message: Optional[str] = None):
        if message is not None:
            self._message = message
        if not self._interactive:
            return self
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        self._finalized = False
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def _spin(self):
        try:
            idx = 0
            while not self._stop.is_set():
                with self._lock:
                    if self._finalized:
                        break
                    self._render(self._chars[idx % len(self._chars)])
                idx += 1
                time.sleep(0.08)
        except Exception:
            pass
        self._stream.write("\033[?25h")
        self._stream.flush()

    def _render(self, spinner: str = ""):
        parts = []
        if spinner:
            parts.append(spinner)
        parts.append(self._message)
        if self._progress is not None:
            parts.append(_bar(self._progress))
            parts.append(f"{int(self._progress * 100)}%")
        self._stream.write(f"\r\033[K\033[?25l{' '.join(parts)}")
        self._stream.flush()

    def update(self, message: Optional[str] = None, progress: Optional[float] = None):
        with self._lock:
            if message is not None:
                self._message = message
            if progress is not None:
                self._progress = max(0.0, min(1.0, progress))

    def _finalize(self, symbol: str, color: str, message: Optional[str] = None):
        with self._lock:
            self._finalized = True
            self._stop.set()
            if message is not None:
                self._message = message
        if self._thread:
            self._thread.join(timeout=1)
        msg = self._message if message is None else message
        if self._interactive:
            self._stream.write(f"\r\033[K\033[?25h{color}{symbol} {msg}\033[0m\n")
        else:
            self._stream.write(f"{symbol} {msg}\n")
        self._stream.flush()

    def succeed(self, message: Optional[str] = None):
        self._finalize("✓", "\033[32m", message)

    def warn(self, message: Optional[str] = None):
        self._finalize("⚠", "\033[33m", message)

    def fail(self, message: Optional[str] = None):
        self._finalize("✗", "\033[31m", message)

    def stop(self, message: Optional[str] = None):
        with self._lock:
            self._finalized = True
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        self._stream.write(f"\r\033[?25h{' ' * 40}\r")
        self._stream.flush()

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.stop()
