import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from utils.platform import get_cache_dir


STREAMING_CACHE_DIR = get_cache_dir() / "mpv"


OPTIMIZED_MPV_ARGS = [
    "--no-terminal",
    "--vo=gpu-next",
    "--profile=fast",
    "--hwdec=no",
    "--sub-auto=all",
    "--cache=yes",
    "--cache-secs=600",
    "--demuxer-max-bytes=300M",
    "--demuxer-max-back-bytes=150M",
    "--demuxer-readahead-secs=30",
    "--stream-lavf-o=fflags=+discardcorrupt",
    "--stream-lavf-o=reconnect=1",
    "--stream-lavf-o=reconnect_streamed=1",
    "--stream-lavf-o=reconnect_delay_max=30",
    "--stream-buffer-size=64M",
    "--no-cache-pause",
    "--video-sync=display-resample",
    "--keep-open=yes",
    "--force-seekable=yes",
]


class PlayerBase:
    name = "base"

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    def play(self, url: str, title: str = "", **kwargs):
        raise NotImplementedError

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                if self.process:
                    self.process.kill()
            self.process = None

    def is_running(self) -> bool:
        if self.process:
            return self.process.poll() is None
        return False

    def cleanup(self):
        self.stop()


class MPVPlayer(PlayerBase):
    name = "mpv"

    def __init__(self, args: Optional[List[str]] = None):
        super().__init__()
        self._extra_args = args or []

    def play(self, url: str, title: str = "", position: float = 0.0,
             quality: str = "1080p", subtitles: Optional[str] = None,
             audio_lang: Optional[str] = None, **kwargs):
        cmd = self._build_command(url, title, position, quality, subtitles, audio_lang)
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            print("mpv not found. Please install mpv.")
            return False

    def _build_command(self, url: str, title: str, position: float,
                        quality: str, subtitles: Optional[str],
                        audio_lang: Optional[str]) -> List[str]:
        ytdl_format = self._get_ytdl_format(quality)

        cmd = ["mpv", url]
        cmd.append(f"--ytdl-format={ytdl_format}")
        cmd.extend(OPTIMIZED_MPV_ARGS)

        if title:
            cmd.append(f"--title=hindi-cli - {title[:80]}")

        if position > 0:
            cmd.append(f"--start={position}")

        if subtitles:
            cmd.append(f"--sub-file={subtitles}")

        if audio_lang:
            cmd.extend(["--alang=" + audio_lang])

        cmd.append(f"--write-filename-in-watch-later-config={STREAMING_CACHE_DIR}")

        if self._extra_args:
            cmd.extend(self._extra_args)

        return cmd

    @staticmethod
    def _get_ytdl_format(quality: str) -> str:
        formats = {
            "2160p": "bestvideo[height<=2160]+bestaudio/best",
            "1440p": "bestvideo[height<=1440]+bestaudio/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best",
            "720p": "bestvideo[height<=720]+bestaudio/best",
            "480p": "bestvideo[height<=480]+bestaudio/best",
            "360p": "bestvideo[height<=360]+bestaudio/best",
            "audio": "bestaudio/best",
        }
        return formats.get(quality, "bestvideo[height<=1080]+bestaudio/best")

    def wait(self):
        if self.process:
            try:
                self.process.wait()
            except KeyboardInterrupt:
                self.stop()


class VLCPlayer(PlayerBase):
    name = "vlc"

    def play(self, url: str, title: str = "", position: float = 0.0,
             quality: str = "1080p", **kwargs):
        cmd = ["vlc", url]
        if position > 0:
            cmd.extend(["--start-time", str(position)])
        if title:
            cmd.extend(["--meta-title", title])

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            print("VLC not found. Please install VLC.")
            return False


def get_player(player_name: str = "mpv", **kwargs) -> PlayerBase:
    if player_name == "mpv":
        extra_args = kwargs.get("mpv_args", [])
        return MPVPlayer(args=extra_args)
    elif player_name == "vlc":
        return VLCPlayer()
    return MPVPlayer()


def find_player() -> Optional[str]:
    for name in ["mpv", "vlc"]:
        if shutil.which(name):
            return name
    return None


class PlayerManager:
    def __init__(self, preferred: str = "mpv"):
        self.preferred = preferred
        self.current: Optional[PlayerBase] = None
        self._players = {}

    def get(self, name: Optional[str] = None) -> PlayerBase:
        name = name or self.preferred
        if name not in self._players:
            self._players[name] = get_player(name)
        return self._players[name]

    def play(self, url: str, **kwargs):
        player = self.get()
        self.current = player
        return player.play(url, **kwargs)

    def stop(self):
        if self.current:
            self.current.stop()
            self.current = None

    def cleanup(self):
        for p in self._players.values():
            p.cleanup()
        self._players.clear()
