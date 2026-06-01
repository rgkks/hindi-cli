import json
import re
import subprocess
from typing import Any, Dict, List, Optional

from providers.base import ChannelProvider, Provider, ProviderRegistry
from utils.cache import cache
from utils.latest import fetch_channel_feed, _make_label
from utils.logger import log


ANIME_CHANNELS = {
    "muse_india": {
        "name": "Muse India",
        "url": "https://www.youtube.com/@MuseIndia",
        "languages": ["Hindi", "English", "Japanese"],
    },
    "muse_asia": {
        "name": "Muse Asia",
        "url": "https://www.youtube.com/@MuseAsia",
        "languages": ["English", "Japanese"],
    },
    "ani_one_asia": {
        "name": "Ani-One Asia",
        "url": "https://www.youtube.com/@AniOneAsia",
        "languages": ["English", "Japanese"],
    },
    "anime_log": {
        "name": "AnimeLog",
        "url": "https://www.youtube.com/@AnimeLog",
        "languages": ["English", "Japanese"],
    },
}


def _fmt_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}:{s:02d}"


def _extract_episode(title: str) -> int:
    for p in [r'(?:Episode|Ep|EP|ep)\s*\.?\s*(\d+)', r'#(\d+)',
              r'Part\s*(\d+)', r'(\d+)\s*/\s*\d+']:
        m = re.search(p, title)
        if m:
            return int(m.group(1))
    return 0


def _search_channel_videos(channel_url: str, query: str = "",
                            limit: int = 30) -> List[Dict[str, Any]]:
    search_url = f"ytsearch{limit}:{query} {channel_url}" if query else channel_url
    try:
        result = subprocess.run([
            "yt-dlp", "--flat-playlist", "--dump-json",
            "--no-warnings", "--ignore-errors",
            "--playlist-end", str(limit), search_url,
        ], capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        items = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = entry.get("id", "")
            dur = int(entry.get("duration", 0))
            ep = _extract_episode(entry.get("title", ""))
            items.append({
                "title": entry.get("title", "Unknown"),
                "id": vid,
                "url": entry.get("webpage_url", f"https://youtube.com/watch?v={vid}"),
                "duration": dur,
                "duration_str": _fmt_duration(dur),
                "thumbnail": entry.get("thumbnail", f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"),
                "episode": ep,
                "type": "anime",
                "label": f"[EP {ep}] {entry.get('title', '')[:70]}" if ep else entry.get("title", "")[:80],
            })
        return items
    except FileNotFoundError:
        log.error("yt-dlp not found")
        return []
    except subprocess.TimeoutExpired:
        log.error("yt-dlp timed out")
        return []
    except Exception as e:
        log.error(f"Channel search error: {e}")
        return []


class AnimeChannelProvider(ChannelProvider):
    category = "anime"

    def search(self, query: str = "", **kwargs) -> List[Dict[str, Any]]:
        limit = kwargs.get("limit", 30)
        return _search_channel_videos(self.channel_url, query, limit)

    def latest(self, limit: int = 30) -> List[Dict[str, Any]]:
        handle = self.channel_url.rstrip("/").split("/")[-1]
        videos, error = fetch_channel_feed(
            self.channel_url, limit,
            channel_name=self.channel_name,
        )
        if error:
            log.warning(f"Anime latest [{self.channel_name}]: {error}")
            return []
        for v in videos:
            ep = _extract_episode(v.get("title", ""))
            v["episode"] = ep
            v["channel_name"] = self.channel_name
            v["provider_name"] = self.name
            v["type"] = "anime"
            ep_str = f"[EP {ep}] " if ep else ""
            v["label"] = f"{ep_str}{_make_label(v)}"
        return videos


def _create_channel_providers():
    for ch_id, ch_info in ANIME_CHANNELS.items():
        provider = AnimeChannelProvider()
        provider.name = f"anime_{ch_id}"
        provider.description = f"{ch_info['name']} anime channel"
        provider.channel_url = ch_info["url"]
        provider.channel_name = ch_info["name"]
        provider.languages = ch_info["languages"]
        ProviderRegistry.register(provider)


_create_channel_providers()


class AnimeGroupProvider(Provider):
    name = "anime"
    description = "All anime channels combined"
    category = "anime"

    def search(self, query: str = "", **kwargs) -> List[Dict[str, Any]]:
        cache_key = f"anime_all:{query.lower()}"
        cached = cache.get(cache_key, max_age=600)
        if cached:
            return cached

        channels = ProviderRegistry.get_channels("anime")
        all_videos = []
        for c in channels.values():
            results = c.search(query, limit=15)
            for r in results:
                r["channel_name"] = c.channel_name
                r["provider_name"] = c.name
            all_videos.extend(results)

        anime_map = {}
        for r in all_videos:
            base = re.sub(
                r'(?:Episode|Ep|EP|ep)\s*\.?\s*\d+|#\d+|Part\s*\d+',
                '', r["title"]
            ).strip().rstrip("- ").strip() or r["title"][:30]
            if base not in anime_map:
                anime_map[base] = {
                    "title": base,
                    "episodes": [],
                    "thumbnail": r["thumbnail"],
                    "episode_count": 0,
                    "latest_episode": 0,
                    "channel_names": set(),
                }
            anime_map[base]["episodes"].append(r)
            anime_map[base]["episode_count"] = len(anime_map[base]["episodes"])
            anime_map[base]["latest_episode"] = max(
                anime_map[base]["latest_episode"], r.get("episode", 0))
            anime_map[base]["channel_names"].add(r.get("channel_name", ""))

        results = []
        for base, info in anime_map.items():
            channels_str = ", ".join(sorted(info["channel_names"]))
            results.append({
                "title": base,
                "thumbnail": info["thumbnail"],
                "episode_count": info["episode_count"],
                "latest_episode": info["latest_episode"],
                "episodes": info["episodes"],
                "channels": channels_str,
                "type": "anime",
                "provider": "anime",
                "label": f"{base} | {info['episode_count']} eps | {channels_str}",
            })

        results.sort(key=lambda x: x["episode_count"], reverse=True)
        cache.set(cache_key, results, ttl=600)
        return results

    @staticmethod
    def get_episodes(anime: Dict[str, Any]) -> List[Dict[str, Any]]:
        eps = anime.get("episodes", [])
        eps.sort(key=lambda x: x.get("episode", 0))
        return eps


ProviderRegistry.register(AnimeGroupProvider())
