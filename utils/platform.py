import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


SYSTEM = platform.system().lower()


def is_linux() -> bool:
    return SYSTEM == "linux"


def is_windows() -> bool:
    return SYSTEM == "windows"


def is_macos() -> bool:
    return SYSTEM == "darwin"


def which(name: str) -> Optional[str]:
    return shutil.which(name)


def check_dependency(name: str, install_hint: str = "") -> bool:
    found = which(name) is not None
    if not found:
        hint = install_hint or _default_install_hint(name)
        print(f"  {name} not found. {hint}")
    return found


def _default_install_hint(name: str) -> str:
    hints = {
        "fzf": "Install: https://github.com/junegunn/fzf#installation",
        "mpv": "Install: https://mpv.io/installation/",
        "vlc": "Install: https://www.videolan.org/vlc/",
        "yt-dlp": "Install: pip install yt-dlp",
        "ueberzugpp": "Optional: https://github.com/jstkdng/ueberzugpp",
    }
    return hints.get(name, f"Please install {name}")


def check_all_dependencies() -> dict:
    deps = {
        "python": sys.version_info >= (3, 8),
        "fzf": check_dependency("fzf"),
        "mpv": check_dependency("mpv"),
        "yt-dlp": check_dependency("yt-dlp"),
    }
    return deps


def get_terminal_size() -> tuple:
    try:
        cols, rows = shutil.get_terminal_size()
        return cols, rows
    except Exception:
        return 80, 24


def open_url(url: str):
    if is_linux():
        subprocess.Popen(["xdg-open", url])
    elif is_macos():
        subprocess.Popen(["open", url])
    elif is_windows():
        os.startfile(url)


def get_app_dir() -> Path:
    if is_linux():
        base = Path.home() / ".local" / "share"
    elif is_macos():
        base = Path.home() / "Library" / "Application Support"
    elif is_windows():
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".local" / "share"
    return base / "hindi-cli"


def get_cache_dir() -> Path:
    if is_linux():
        base = Path.home() / ".cache"
    elif is_macos():
        base = Path.home() / "Library" / "Caches"
    elif is_windows():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".cache"
    return base / "hindi-cli"


def supports_kitty() -> bool:
    term = os.environ.get("TERM", "")
    return "kitty" in term


def supports_ueberzug() -> bool:
    return which("ueberzugpp") is not None


def supports_thumbnails() -> bool:
    return supports_kitty() or supports_ueberzug()
