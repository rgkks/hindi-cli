import json
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from providers.base import ChannelProvider, ProviderRegistry
from utils.cache import cache
from utils.logger import log
from utils.platform import ytdl_cookie_args


CACHE_TTL = 300
MAX_WORKERS = 4
FETCH_TIMEOUT = 60
SEARCH_TIMEOUT = 30
YTDLP_ARGS = [
    "yt-dlp", "--flat-playlist", "--dump-json",
    "--no-warnings", "--ignore-errors",
    "--extractor-args", "youtubetab:approximate_date",
]

_channel_id_cache: Dict[str, str] = {}
_channel_id_cache_lock = threading.Lock()


def _fmt_date(upload_date: str) -> str:
    if not upload_date or len(upload_date) != 8:
        return "?"
    try:
        dt = datetime.strptime(upload_date, "%Y%m%d")
        now = datetime.now()
        diff = now - dt
        if diff.days == 0:
            return "Today"
        if diff.days == 1:
            return "Yesterday"
        if diff.days < 7:
            return f"{diff.days}d ago"
        if diff.days < 30:
            return f"{diff.days // 7}w ago"
        return dt.strftime("%d %b")
    except ValueError:
        return upload_date


def _parse_upload_date(upload_date: str) -> int:
    if not upload_date or len(upload_date) != 8:
        return 0
    try:
        dt = datetime.strptime(upload_date, "%Y%m%d")
        return int(dt.timestamp())
    except ValueError:
        return 0


def _fmt_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}:{s:02d}"


def _fmt_latest_label(entry: Dict[str, Any], channel_name: str = "") -> str:
    title = entry.get("title", "Unknown")[:55]
    date_str = _fmt_date(entry.get("upload_date", ""))
    dur_str = _fmt_duration(int(entry.get("duration") or 0))
    ch = f" [{channel_name}]" if channel_name else ""
    return f"{title}  {date_str}  {dur_str}{ch}"


def _extract_channel_handle(url: str) -> str:
    m = re.search(r'youtube\.com/@([\w-]+)', url)
    return m.group(1) if m else ""


def _search_channel_id(channel_name: str) -> Optional[str]:
    with _channel_id_cache_lock:
        cached = _channel_id_cache.get(channel_name)
        if cached:
            return cached

    search_query = f"ytsearch5:{channel_name} channel"
    try:
        result = subprocess.run(
            ["yt-dlp"] + ytdl_cookie_args() + ["--flat-playlist", "--dump-json",
             "--no-warnings", "--ignore-errors",
             "--playlist-end", "5", search_query],
            capture_output=True, text=True, timeout=SEARCH_TIMEOUT,
        )
        best_id = None
        best_confidence = 0
        name_lower = channel_name.lower()
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ch_url = entry.get("channel_url", "") or ""
            m = re.search(r'/channel/(UC[\w-]+)', ch_url)
            if not m:
                continue
            channel_id = m.group(1)
            ch = (entry.get("channel") or entry.get("uploader") or "").lower()
            if not ch:
                best_id = channel_id
                continue

            confidence = 0
            if name_lower == ch:
                confidence = 100
            elif name_lower in ch or ch in name_lower:
                confidence = 50
            elif any(word in ch for word in name_lower.split()):
                confidence = 25

            if confidence > best_confidence:
                best_confidence = confidence
                best_id = channel_id

        if best_id and best_confidence >= 25:
            with _channel_id_cache_lock:
                _channel_id_cache[channel_name] = best_id
            log.info(f"Resolved {channel_name} -> channel/{best_id} (confidence={best_confidence})")
            return best_id

        if best_id and best_confidence == 0:
            with _channel_id_cache_lock:
                _channel_id_cache[channel_name] = best_id
            log.info(f"Resolved {channel_name} -> channel/{best_id} (low confidence, no name match)")
            return best_id

    except Exception as e:
        log.debug(f"Search for {channel_name} failed: {e}")
    return None


def _run_ytdlp(url: str, limit: int) -> Tuple[str, Optional[str]]:
    try:
        result = subprocess.run(
            YTDLP_ARGS[:1] + ytdl_cookie_args() + YTDLP_ARGS[1:] + ["--playlist-end", str(limit), url],
            capture_output=True, text=True, timeout=FETCH_TIMEOUT,
        )
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()

        if result.returncode != 0 and not stdout:
            msg = stderr[:200] if stderr else f"yt-dlp returned {result.returncode}"
            return "", msg

        if result.returncode != 0 and stdout:
            log.warning(f"yt-dlp partial for {url[:60]}: {stderr[:100]}")

        return stdout, None

    except FileNotFoundError:
        return "", "yt-dlp not found"
    except subprocess.TimeoutExpired:
        return "", f"yt-dlp timed out after {FETCH_TIMEOUT}s"
    except Exception as e:
        return "", str(e)


def search_channel_videos_raw(channel_url: str, query: str = "",
                               limit: int = 30) -> List[Dict[str, Any]]:
    search_url = f"ytsearch{limit}:{query} {channel_url}" if query else channel_url
    try:
        result = subprocess.run(
            ["yt-dlp"] + ytdl_cookie_args() + ["--flat-playlist", "--dump-json",
             "--no-warnings", "--ignore-errors",
             "--playlist-end", str(limit), search_url],
            capture_output=True, text=True, timeout=60)
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
            dur = int(entry.get("duration") or 0)
            items.append({
                "title": entry.get("title", "Unknown"),
                "id": vid,
                "url": entry.get("webpage_url", f"https://youtube.com/watch?v={vid}"),
                "duration": dur,
                "duration_str": _fmt_duration(dur),
                "thumbnail": entry.get("thumbnail", f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"),
                "view_count": entry.get("view_count", 0),
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


def make_label(entry: Dict[str, Any]) -> str:
    title = entry.get("title", "Unknown")[:55]
    date_str = _fmt_date(entry.get("upload_date", "") or "")
    dur_str = _fmt_duration(int(entry.get("duration") or 0))
    return f"{title}  {date_str}  {dur_str}"


def parse_video_entries(stdout: str) -> List[Dict[str, Any]]:
    items = []
    for line in stdout.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            log.warning(f"Failed to parse JSON line: {line[:80]}")
            continue
        vid = entry.get("id", "")
        if not vid:
            continue
        upload_date = entry.get("upload_date", "") or ""
        timestamp = _parse_upload_date(upload_date)
        dur = int(entry.get("duration") or 0)
        items.append({
            "title": entry.get("title", "Unknown"),
            "id": vid,
            "url": entry.get("webpage_url",
                             f"https://youtube.com/watch?v={vid}"),
            "duration": dur,
            "duration_str": _fmt_duration(dur),
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "upload_date": upload_date,
            "timestamp": timestamp,
            "label": make_label(entry),
        })
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items


def fetch_channel_feed(channel_url: str, limit: int = 30,
                       channel_name: str = ""
                       ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    first_error = ""

    base = channel_url.rstrip("/")
    videos_url = base if base.endswith("/videos") else base + "/videos"
    stdout, first_error = _run_ytdlp(videos_url, limit)
    if not first_error and stdout:
        return parse_video_entries(stdout), None

    log.info(f"Feed /videos failed for {channel_url}: {first_error}")
    stdout, first_error = _run_ytdlp(channel_url, limit)
    if not first_error and stdout:
        return parse_video_entries(stdout), None

    handle = _extract_channel_handle(channel_url)
    search_name = channel_name or handle
    if search_name:
        log.info(f"Resolving {search_name} via search...")
        channel_id = _search_channel_id(search_name)
        if channel_id:
            id_url = f"https://www.youtube.com/channel/{channel_id}/videos"
            log.info(f"Resolved {search_name} -> channel/{channel_id}")
            stdout, err = _run_ytdlp(id_url, limit)
            if not err and stdout:
                return parse_video_entries(stdout), None
            first_error = f"{first_error}; channel ID also failed: {err}"
        else:
            first_error = f"{first_error}; search found no channel ID for {search_name}"

    return [], first_error or "channel returned no videos"


class LatestFetcher:
    def __init__(self, category: str, refresh_interval: int = CACHE_TTL):
        self.category = category
        self.refresh_interval = refresh_interval
        self._cache: List[Dict[str, Any]] = []
        self._last_fetch: float = 0
        self._status: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        self._refresh_timer: Optional[threading.Timer] = None

    def _get_providers(self) -> Dict[str, ChannelProvider]:
        return ProviderRegistry.get_channels(self.category)

    def fetch(self, force: bool = False,
              time_filter: str = "",
              provider_filter: str = "") -> List[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            if not force and self._cache and (now - self._last_fetch) < self.refresh_interval:
                return self._apply_filters(self._cache, time_filter, provider_filter)

        providers = self._get_providers()
        if not providers:
            return []

        all_videos: List[Dict[str, Any]] = []
        self._status = {}
        fetch_start = time.time()

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(self._fetch_one, name, p): name
                for name, p in providers.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    videos, error = future.result()
                    if error:
                        self._status[name] = {
                            "ok": False, "error": error, "count": 0
                        }
                        log.warning(f"Latest [{self.category}/{name}]: {error}")
                    else:
                        self._status[name] = {
                            "ok": True, "error": None, "count": len(videos)
                        }
                        p = providers[name]
                        for v in videos:
                            v["channel_name"] = p.channel_name
                            v["provider_name"] = name
                            v["type"] = self.category
                            v["label"] = _fmt_latest_label(v, p.channel_name)
                        all_videos.extend(videos)
                        log.info(
                            f"Latest [{self.category}/{name}]: "
                            f"{len(videos)} videos"
                        )
                except Exception as e:
                    self._status[name] = {
                        "ok": False, "error": str(e), "count": 0
                    }
                    log.error(f"Latest [{self.category}/{name}]: {e}")

        all_videos.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

        seen: Dict[str, bool] = {}
        deduped = []
        for v in all_videos:
            vid = v.get("id", "")
            if vid not in seen:
                seen[vid] = True
                deduped.append(v)

        elapsed = time.time() - fetch_start
        ok_count = sum(
            1 for s in self._status.values() if s["ok"]
        )
        total = len(self._status)
        log.info(
            f"Latest [{self.category}]: {len(deduped)} videos from "
            f"{ok_count}/{total} providers in {elapsed:.1f}s"
        )

        with self._lock:
            self._cache = deduped
            self._last_fetch = time.time()

        return self._apply_filters(deduped, time_filter, provider_filter)

    def _fetch_one(self, name: str, provider: ChannelProvider
                   ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        try:
            return fetch_channel_feed(
                provider.channel_url, limit=30,
                channel_name=provider.channel_name,
            )
        except Exception as e:
            return [], str(e)

    def _apply_filters(self, videos: List[Dict[str, Any]],
                       time_filter: str = "",
                       provider_filter: str = "") -> List[Dict[str, Any]]:
        result = videos
        now_ts = time.time()

        if time_filter:
            cutoff = now_ts
            if time_filter == "24h":
                cutoff = now_ts - 86400
            elif time_filter == "7d":
                cutoff = now_ts - 86400 * 7
            elif time_filter == "30d":
                cutoff = now_ts - 86400 * 30
            result = [v for v in result
                      if v.get("timestamp", 0) >= cutoff]

        if provider_filter:
            result = [v for v in result
                      if v.get("provider_name", "") == provider_filter]

        return result

    def get_status(self) -> Dict[str, Dict]:
        return dict(self._status)

    def get_provider_status_summary(self) -> str:
        parts = []
        for name, status in self._status.items():
            p = ProviderRegistry.get(name)
            label = p.channel_name if p else name
            if status["ok"]:
                parts.append(f"  ✓ {label} ({status['count']} videos)")
            else:
                parts.append(f"  ✗ {label} ({status['error']})")
        return "\n".join(parts) if parts else "  (no providers)"

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = []
            self._last_fetch = 0


_fetchers: Dict[str, LatestFetcher] = {}
_fetchers_lock = threading.Lock()


def get_latest_fetcher(category: str,
                       refresh_interval: int = CACHE_TTL) -> LatestFetcher:
    with _fetchers_lock:
        if category not in _fetchers:
            _fetchers[category] = LatestFetcher(category, refresh_interval)
        return _fetchers[category]


def invalidate_all_caches() -> None:
    with _fetchers_lock:
        for f in _fetchers.values():
            f.invalidate_cache()
