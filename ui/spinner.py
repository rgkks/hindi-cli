import itertools
import sys
import threading
import time


SPINNER_CHARS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Spinner:
    def __init__(self, message: str = "Loading", stream=sys.stderr):
        self.message = message
        self.stream = stream
        self._running = False
        self._thread: threading.Thread = None

    def _spin(self):
        for c in itertools.cycle(SPINNER_CHARS):
            if not self._running:
                break
            self.stream.write(f"\r\033[?25l{c} {self.message}...  ")
            self.stream.flush()
            time.sleep(0.08)
        self.stream.write(f"\r\033[?25h{' ' * (len(self.message) + 8)}\r")
        self.stream.flush()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, final_message: str = ""):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        if final_message:
            self.stream.write(f"\r{final_message}\n")
            self.stream.flush()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
