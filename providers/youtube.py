import json
import subprocess
from typing import Any, Dict, List, Optional

from providers.base import Provider, ProviderRegistry
from utils.cache import cache
from utils.logger import log
from utils.platform import ytdl_cookie_args


class YouTubeProvider(Provider):
    name = "youtube"
    description = "YouTube search and playback via yt-dlp"
    category = "video"
    cache_ttl = 600

    def _run_ytdlp(self, args: List[str]) -> Optional[List[Dict]]:
        try:
            result = subprocess.run(
                ["yt-dlp"] + ytdl_cookie_args() + args,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None
            results = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return results or None
        except FileNotFoundError:
            log.error("yt-dlp not found")
            return None
        except subprocess.TimeoutExpired:
            log.error("yt-dlp timed out")
            return None
        except Exception as e:
            log.error(f"yt-dlp error: {e}")
            return None

    def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        cached = cache.get(f"yt_s:{query.lower()}", max_age=300)
        if cached:
            return cached
        limit = kwargs.get("limit", 15)
        data = self._run_ytdlp([
            "--flat-playlist", "--dump-json", "--no-warnings",
            "--ignore-errors", "--playlist-end", str(limit),
            f"ytsearch{limit}:{query}",
        ])
        results = self._parse_results(data)
        cache.set(f"yt_s:{query.lower()}", results, ttl=300)
        return results

    def _parse_results(self, data: Optional[List[Dict]]) -> List[Dict[str, Any]]:
        results = []
        if not data:
            return results
        for entry in data:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title", "Unknown")
            video_id = entry.get("id", "")
            url = entry.get("webpage_url", f"https://youtube.com/watch?v={video_id}")
            duration = int(entry.get("duration") or 0)
            view_count = entry.get("view_count", 0)
            uploader = entry.get("uploader", entry.get("channel", "Unknown"))

            mins, secs = divmod(duration, 60)
            hours, mins = divmod(mins, 60)
            dur_str = f"{hours}h{mins:02d}m{secs:02d}s" if hours else f"{mins:02d}:{secs:02d}"

            results.append({
                "title": title,
                "id": video_id,
                "url": url,
                "duration": duration,
                "duration_str": dur_str,
                "views": view_count,
                "views_str": self._fmt(view_count),
                "uploader": uploader,
                "type": "youtube",
                "provider": "youtube",
                "label": f"{title} [{dur_str}] - {uploader}",
            })
        return results

    @staticmethod
    def _fmt(count: int) -> str:
        if count >= 1_000_000_000:
            return f"{count/1_000_000_000:.1f}B"
        if count >= 1_000_000:
            return f"{count/1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count/1_000:.1f}K"
        return str(count)

    def get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        cached = cache.get(f"vi:{url}", max_age=3600)
        if cached:
            return cached
        data = self._run_ytdlp(["--dump-json", "--no-warnings", url])
        if data:
            result = self._parse_results(data)
            if result:
                cache.set(f"vi:{url}", result[0], ttl=3600)
                return result[0]
        return None


ProviderRegistry.register(YouTubeProvider())
