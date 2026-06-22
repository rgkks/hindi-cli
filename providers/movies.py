import json
import subprocess
from typing import Any, Dict, List, Optional

from providers.base import ChannelProvider, Provider, ProviderRegistry
from utils.cache import cache
from utils.latest import fetch_channel_feed, search_channel_videos_raw, make_label as _make_label
from utils.logger import log


MOVIE_CHANNELS = {
    "goldmines": {
        "name": "Goldmines Telefilms",
        "url": "https://www.youtube.com/@GoldminesTelefilms",
        "languages": ["Hindi"],
    },
    "shemaroo": {
        "name": "Shemaroo Movies",
        "url": "https://www.youtube.com/@ShemarooMovies",
        "languages": ["Hindi"],
    },
    "premium_digiplex": {
        "name": "Premium Digiplex Movies",
        "url": "https://www.youtube.com/@PremiumDigiplexMovies",
        "languages": ["Hindi"],
    },
    "yrf": {
        "name": "YRF (Yash Raj Films)",
        "url": "https://www.youtube.com/@yrf",
        "languages": ["Hindi", "English"],
    },
    "shemaroo_tamil": {
        "name": "Shemaroo Tamil",
        "url": "https://www.youtube.com/@ShemarooTamil",
        "languages": ["Tamil"],
    },
    "shemaroo_telugu": {
        "name": "Shemaroo Telugu",
        "url": "https://www.youtube.com/@ShemarooTelugu",
        "languages": ["Telugu"],
    },
}


def _fmt_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m:02d}:{s:02d}"


def _fmt_views(count: int) -> str:
    if count >= 1_000_000_000:
        return f"{count/1_000_000_000:.1f}B"
    if count >= 1_000_000:
        return f"{count/1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count/1_000:.1f}K"
    return str(count)


def _search_channel_videos(channel_url: str, query: str = "",
                            limit: int = 30) -> List[Dict[str, Any]]:
    items = search_channel_videos_raw(channel_url, query, limit)
    for item in items:
        views = item.get("view_count", 0)
        item["views"] = views
        item["views_str"] = _fmt_views(views)
        item["type"] = "movie"
        item["label"] = f"{item['title'][:70]} [{item['duration_str']}] - {_fmt_views(views)} views"
    return items


class MovieChannelProvider(ChannelProvider):
    category = "movies"

    def search(self, query: str = "", **kwargs) -> List[Dict[str, Any]]:
        limit = kwargs.get("limit", 30)
        return _search_channel_videos(self.channel_url, query, limit)

    def latest(self, limit: int = 30) -> List[Dict[str, Any]]:
        videos, error = fetch_channel_feed(
            self.channel_url, limit,
            channel_name=self.channel_name,
        )
        if error:
            log.warning(f"Movie latest [{self.channel_name}]: {error}")
            return []
        for v in videos:
            v["channel_name"] = self.channel_name
            v["provider_name"] = self.name
            v["type"] = "movie"
            v["label"] = _make_label(v)
        return videos


def _create_channel_providers():
    for ch_id, ch_info in MOVIE_CHANNELS.items():
        provider = MovieChannelProvider()
        provider.name = f"movies_{ch_id}"
        provider.description = f"{ch_info['name']} movies channel"
        provider.channel_url = ch_info["url"]
        provider.channel_name = ch_info["name"]
        provider.languages = ch_info["languages"]
        ProviderRegistry.register(provider)


_create_channel_providers()


class MovieGroupProvider(Provider):
    name = "movies"
    description = "All movie channels combined"
    category = "movies"

    def search(self, query: str = "", **kwargs) -> List[Dict[str, Any]]:
        lang = kwargs.get("language", "")
        cache_key = f"movie_all:{query.lower()}:{lang}"
        cached = cache.get(cache_key, max_age=600)
        if cached:
            return cached

        channels = ProviderRegistry.get_channels("movies")
        all_videos = []
        for c in channels.values():
            if lang and lang.lower() not in [l.lower() for l in c.languages]:
                continue
            results = c.search(query, limit=15)
            for r in results:
                r["channel_name"] = c.channel_name
                r["provider_name"] = c.name
                r["label"] = f"{r['title']} [{r['duration_str']}] - {c.channel_name}"
            all_videos.extend(results)

        sort_by = kwargs.get("sort", "")
        if sort_by == "popular":
            all_videos.sort(key=lambda x: x.get("views", 0), reverse=True)
        elif sort_by == "duration":
            all_videos.sort(key=lambda x: x.get("duration", 0), reverse=True)

        cache.set(cache_key, all_videos, ttl=600)
        return all_videos


ProviderRegistry.register(MovieGroupProvider())
