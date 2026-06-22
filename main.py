#!/usr/bin/env python3

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import Config, CONFIG_PATH as CONFIG_FILE_PATH
from core.database import db
from core.fzf import FZF
from providers.base import ChannelProvider, ProviderRegistry
import providers.youtube
import providers.anime
import providers.movies
from ui.menu import (
    show_main_menu, show_submenu, show_search_results,
    show_provider_list, show_quality_menu, show_action_menu,
    show_language_filter, show_sort_options, show_continue_menu,
    show_text_input, show_time_filter,
    show_error, show_success, show_info, show_warning,
)
from ui.status import Status
from utils.latest import get_latest_fetcher, invalidate_all_caches
from utils.logger import log, setup_logger
from utils.platform import open_url, get_cache_dir, get_app_dir, which, ytdl_cookie_args
from utils.preload import PRELOAD_FORMATS, Preloader, _parse_progress
from version import __version__, __version_display__, version_string, about_string, is_newer


MPV_ARGS = [
    "--no-terminal",
    "--vo=gpu-next",
    "--hwdec=auto-safe",
    "--gpu-context=auto",
    "--opengl-pbo=yes",
    "--sub-auto=all",
    "--cache=yes",
    "--cache-secs=600",
    "--cache-pause=yes",
    "--cache-pause-wait=10",
    "--demuxer-max-bytes=512M",
    "--demuxer-max-back-bytes=256M",
    "--demuxer-readahead-secs=120",
    "--stream-buffer-size=128M",
    "--stream-lavf-o=fflags=+discardcorrupt",
    "--stream-lavf-o=reconnect=1",
    "--stream-lavf-o=reconnect_streamed=1",
    "--stream-lavf-o=reconnect_delay_max=30",
    "--vd-lavc-threads=0",
    "--vd-lavc-software-fallback=yes",
    "--video-sync=audio",
    "--keep-open=yes",
    "--force-seekable=yes",
]

YTDL_FORMATS = {
    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "best[height<=480]",
    "360p": "best[height<=360]",
    "audio": "bestaudio/best",
}

TIME_FILTER_MAP = {
    "All time": "",
    "Last 24 hours": "24h",
    "Last 7 days": "7d",
    "Last 30 days": "30d",
}


def _splash() -> None:
    print("\033[2J\033[H", end="")
    print("  ╔══════════════════════════════════════╗")
    print(f"  ║     \U0001f3ac hindi-cli {__version_display__:<10}         ║")
    print("  ║     YouTube \u2022 Anime \u2022 Movies         ║")
    print("  ╚══════════════════════════════════════╝")
    print()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def _show_history() -> None:
    items = db.get_history(limit=50)
    if not items:
        show_info("No watch history")
        return
    print(f"\n  Watch History ({len(items)} entries):\n")
    for i, item in enumerate(items, 1):
        dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(item["watched_at"]))
        print(f"  {i:>3}. [{item['media_type']}] {item['title'][:60]}")
        print(f"       {dt}")
    print()


def _show_stats() -> None:
    data = db.get_stats()
    print()
    print(f"  \u2699 hindi-cli Statistics")
    print(f"  {'─' * 40}")
    print(f"  Total watch history:  {data.get('total_watched', 0)}")
    print(f"  Videos watched:       {data.get('videos', 0)}")
    print(f"  Anime episodes:       {data.get('anime', 0)}")
    print(f"  Movies watched:       {data.get('movies', 0)}")
    print(f"  Liked videos:         {data.get('liked', 0)}")
    print(f"  Anime in progress:    {data.get('anime_in_progress', 0)}")
    print(f"  Movies in progress:   {data.get('movies_in_progress', 0)}")
    print()


def _doctor() -> None:
    print()
    print(f"  \u2699 hindi-cli Diagnostics")
    print(f"  {'─' * 50}")
    print(f"  Version:    {version_string()}")
    print(f"  Python:     {sys.version.split()[0]} ({sys.executable})")
    print(f"  Platform:   {sys.platform}")
    print(f"  Config:     {CONFIG_FILE_PATH}")
    print(f"  Data:       {get_app_dir()}")
    print(f"  Cache:      {get_cache_dir()}")
    log_path = "N/A"
    if log.handlers:
        h = log.handlers[0]
        log_path = getattr(h, "baseFilename", "N/A")
    print(f"  Log:        {log_path}")
    print()

    checks = [
        ("mpv",       which("mpv"),       "https://mpv.io/installation/"),
        ("fzf",       which("fzf"),       "https://github.com/junegunn/fzf#installation"),
        ("yt-dlp",    which("yt-dlp"),    "pip install yt-dlp"),
        ("ffmpeg",    which("ffmpeg"),    "https://ffmpeg.org/download.html"),
        ("vlc",       which("vlc"),       "https://www.videolan.org/vlc/"),
    ]
    all_ok = True
    for name, path, hint in checks:
        if path:
            print(f"  \u2713 {name:<12} {path}")
        else:
            print(f"  \u2717 {name:<12} not found — {hint}")
            all_ok = False

    print()
    config_ok = CONFIG_FILE_PATH.exists()
    print(f"  {'\u2713' if config_ok else '\u2717'} Config file: {'exists' if config_ok else 'missing'}")
    db_path = get_app_dir() / "history.db"
    db_ok = db_path.exists()
    print(f"  {'\u2713' if db_ok else '\u2717'} Database:    {'exists' if db_ok else 'not yet created'} ({db_path})")
    cache_dir = get_cache_dir()
    cache_ok = cache_dir.exists()
    print(f"  {'\u2713' if cache_ok else '\u2717'} Cache dir:   {'exists' if cache_ok else 'not yet created'} ({cache_dir})")

    print()
    status = _check_network()
    if status:
        print(f"  \u2713 Network:    reachable")
    else:
        print(f"  \u2717 Network:    unreachable — check your internet connection")

    print()
    print(f"  Summary: {'All checks passed' if all_ok else 'Some dependencies missing'}")

    if not all_ok:
        print()
        print(f"  Install missing deps: ./install.sh")
    print()


def _check_network() -> bool:
    try:
        import httpx
        r = httpx.get("https://www.youtube.com", follow_redirects=True, timeout=5)
        return r.is_success
    except ImportError:
        return False
    except Exception:
        return False


def _check_update() -> None:
    print()
    print(f"  Checking for updates...")
    try:
        import httpx
        r = httpx.get(
            "https://api.github.com/repos/rgkks/hindi-cli/releases/latest",
            timeout=10,
        )
        if r.is_success:
            data = r.json()
            latest = data.get("tag_name", "").lstrip("v")
            current = __version__
            if latest and is_newer(latest, current):
                print(f"  \u2191 Update available: {latest} (current: {__version_display__})")
                print(f"  \u2192 https://github.com/rgkks/hindi-cli/releases")
            elif latest:
                print(f"  \u2713 You're up to date ({__version_display__})")
            else:
                print(f"  \u2713 {__version_display__}")
        else:
            print(f"  \u2717 Could not check for updates (HTTP {r.status_code})")
    except Exception as e:
        print(f"  \u2717 Update check failed: {e}")
    print()


def _clear_cache() -> None:
    from utils.cache import cache
    from utils.preload import Preloader

    cache.clear()
    Preloader.cleanup_all()
    show_success("Cache cleared")


def _show_config() -> None:
    path = CONFIG_FILE_PATH
    if path.exists():
        print(f"\n  Config: {path}\n")
        print(path.read_text())
    else:
        show_info(f"Config not found. Default config would be at {path}")
    print(f"  Edit with: $EDITOR {path}")


# ---------------------------------------------------------------------------
# Core flows
# ---------------------------------------------------------------------------

def check_deps() -> None:
    for name, hint in [("fzf", "apt/brew install fzf"),
                        ("mpv", "apt/brew install mpv"),
                        ("yt-dlp", "pip install yt-dlp")]:
        if not shutil.which(name):
            print(f"Missing: {name} ({hint})")
            sys.exit(1)


def sig_handler(sig: int, frame: object) -> None:
    print("\nExiting...")
    raise KeyboardInterrupt


def _handle_video_action(item: Dict[str, Any],
                         category: str = "video") -> bool:
    act = show_action_menu(item.get("title", "Video"))
    if not act or act == "Back":
        return False
    if act == "Copy URL":
        url = item.get("url", "")
        try:
            import pyperclip
            pyperclip.copy(url)
            show_success("Copied")
        except ImportError:
            print(url)
        return True
    if act == "Open in browser":
        open_url(item.get("url", ""))
        return True
    if act == "Like":
        db.add_liked(item["url"], item["title"], category)
        show_success("Liked")
        return True
    if act == "Download":
        q = show_quality_menu()
        if q:
            dl_video(item, q)
        return True
    if act == "Play now":
        q = show_quality_menu()
        if q:
            db.add_to_history(category, item["title"], item["url"],
                              provider=item.get("provider", category))
            play_video(item, q)
        return True
    return True


def search_yt() -> None:
    query = show_text_input("Search YouTube: ")
    if not query:
        return
    provider = ProviderRegistry.get("youtube")
    if not provider:
        show_error("Provider unavailable")
        return
    status = Status("Searching YouTube", style="dots")
    status.start()
    try:
        results = provider.search(query)
    except Exception as e:
        status.fail("Search failed")
        show_error(str(e))
        return
    status.succeed(f"Found {len(results)} results")
    if not results:
        return
    selected = show_search_results(results, "YouTube Search")
    if selected:
        _handle_video_action(selected, "youtube")


def history_flow() -> None:
    while True:
        act = show_submenu("History & Likes", [
            ("Watch History", "h"), ("Liked Videos", "l"),
            ("Continue Watching", "c"), ("Clear History", "x"), ("Go Back", "b"),
        ])
        if not act or act == "b":
            break
        if act == "h":
            items = db.get_history("youtube")
            if items:
                sel = show_continue_menu(items, "History")
                if sel:
                    play_video(sel, Config().quality, position=sel.get("position", 0))
            else:
                show_info("Empty")
        elif act == "l":
            liked = db.get_liked("youtube")
            if liked:
                lst = [{"title": l["title"], "url": l["url"], "label": l["title"]} for l in liked]
                sel = show_search_results(lst, "Liked")
                if sel:
                    q = show_quality_menu()
                    if q:
                        play_video(sel, q)
            else:
                show_info("No likes")
        elif act == "c":
            items = db.get_history("youtube", 20)
            if items:
                sel = show_continue_menu(items, "Continue")
                if sel:
                    play_video(sel, Config().quality, position=sel.get("position", 0))
            else:
                show_info("Nothing")
        elif act == "x":
            if FZF.confirm("Clear YouTube history?"):
                db.clear_history("youtube")
                show_success("Cleared")


def yt_flow() -> None:
    while True:
        act = show_submenu("YouTube", [
            ("Search YouTube", "s"), ("History & Likes", "h"), ("Go Back", "b"),
        ])
        if not act or act == "b":
            break
        if act == "s":
            search_yt()
        elif act == "h":
            history_flow()


def search_anime(provider_name: str = "anime"):
    query = show_text_input("Search Anime: ")
    if not query:
        return
    status = Status("Searching Anime", style="dots")
    status.start()
    provider = ProviderRegistry.get(provider_name)
    if not provider:
        status.fail("Provider unavailable")
        return
    try:
        results = provider.search(query)
    except Exception as e:
        status.fail("Search failed")
        return
    status.succeed(f"Found {len(results)} results")
    if not results:
        return

    if isinstance(provider, ChannelProvider):
        for item in results:
            item["provider"] = provider.name
            item["type"] = "anime"
        sel = show_search_results(results, f"{provider.channel_name}")
        if sel:
            _handle_video_action(sel, "anime")
        return

    sel = show_search_results(
        [{"title": r["title"], "label": r["label"]} for r in results], "Anime")
    if not sel:
        return
    anime = None
    for r in results:
        if sel["title"] == r["title"] or sel.get("label") == r.get("label", ""):
            anime = r
            break
    if not anime:
        return
    episodes = provider.get_episodes(anime)
    if not episodes:
        show_error("No episodes")
        return
    eps = [{"title": e["title"], "label": e["label"], "url": e["url"],
            "episode": e.get("episode", 0), "type": "anime",
            "anime_id": anime["title"].replace(" ", "_").lower()} for e in episodes]
    ep = show_search_results(eps, "Episodes")
    if not ep:
        return
    ep_data = None
    for e in episodes:
        if ep["title"] == e["title"]:
            ep_data = e
            break
    if not ep_data:
        return
    q = show_quality_menu()
    if not q:
        return
    db.add_to_history("anime", anime["title"], ep_data["url"],
                      provider="anime", episode=ep_data.get("episode", 0))
    db.update_anime_progress(anime["title"].replace(" ", "_").lower(),
                              anime["title"], ep_data.get("episode", 0),
                              0, 0, provider="anime", url=ep_data["url"])
    play_video(ep_data, q, title=f"{anime['title']} - EP {ep_data.get('episode', 0)}")


def continue_anime() -> None:
    items = db.get_all_anime_progress()
    if not items:
        show_info("No progress")
        return
    lst = [{"title": p["title"], "position": p.get("position", 0),
            "duration": max(p.get("duration", 1), 1),
            "provider": p.get("provider", ""), "url": p.get("url", ""),
            "episode": p.get("episode", 0), "type": "anime",
            "anime_id": p.get("anime_id", p.get("id", p["url"].split("/")[-1]))} for p in items]
    sel = show_continue_menu(lst, "Continue Anime")
    if not sel:
        return
    q = show_quality_menu()
    if q:
        play_video(sel, q, position=sel.get("position", 0),
                   title=f"{sel['title']} - EP {sel.get('episode', 0)}")


def _run_latest_flow(fetcher, category: str, title: str):
    time_filter = ""
    while True:
        status = Status(f"Fetching latest {category}", style="dots")
        status.start()
        results = fetcher.fetch(force=False, time_filter=time_filter)
        status.succeed(f"Found {len(results)} results")

        if not results:
            status = fetcher.get_provider_status_summary()
            show_warning(f"No results. Provider status:\n{status}")
            break

        sel = show_search_results(results, title)
        if sel is None:
            break

        if sel.get("_action") == "refresh":
            fetcher.invalidate_cache()
            continue
        if sel.get("_action") == "filter_time":
            raw = show_time_filter()
            if raw and raw != "All time":
                time_filter = TIME_FILTER_MAP.get(raw, "")
                fetcher.invalidate_cache()
            continue
        if sel.get("_action") == "status":
            status = fetcher.get_provider_status_summary()
            show_info(f"Provider status:\n{status}")
            input("Press Enter to continue...")
            continue

        sel["provider"] = sel.get("provider_name", category)
        sel["type"] = category
        _handle_video_action(sel, category)


def latest_anime_flow() -> None:
    fetcher = get_latest_fetcher("anime")
    _run_latest_flow(fetcher, "anime", "Latest Anime")


def latest_movies_flow() -> None:
    fetcher = get_latest_fetcher("movies")
    _run_latest_flow(fetcher, "movies", "Latest Movies")


def browse_anime_providers():
    while True:
        providers = ProviderRegistry.get_channels("anime")
        if not providers:
            show_error("No providers")
            return
        sel = show_provider_list(providers, "Anime Providers")
        if not sel:
            return
        act = show_submenu(sel.channel_name, [
            ("Search in channel", "s"), ("Latest videos", "l"), ("Go Back", "b"),
        ])
        if not act or act == "b":
            continue
        if act == "s":
            search_anime(provider_name=sel.name)
        elif act == "l":
            status = Status(f"Loading {sel.channel_name}", style="dots")
            status.start()
            try:
                results = sel.latest()
            except Exception as e:
                status.fail("Failed")
                show_error(f"Fetch error: {e}")
                log.error(f"Latest [{sel.name}]: {e}")
                continue
            count = len(results)
            status.succeed(f"Found {count} videos" if count else "No videos")
            if not results:
                show_warning(f"{sel.channel_name}: no videos found. "
                             "The channel may be blocked or "
                             "temporarily unavailable.")
                log.warning(f"Latest [{sel.name}]: empty result for "
                            f"{sel.channel_url}")
                continue
            for item in results:
                item["provider"] = sel.name
            chosen = show_search_results(results, f"{sel.channel_name} - Latest")
            if chosen:
                _handle_video_action(chosen, "anime")


def anime_flow() -> None:
    while True:
        act = show_submenu("Anime", [
            ("Search Anime", "s"), ("Latest Anime", "l"),
            ("Browse Anime Providers", "b"),
            ("Continue Anime", "c"),
            ("Clear History", "x"), ("Go Back", "g"),
        ])
        if not act or act == "g":
            break
        if act == "s":
            search_anime()
        elif act == "l":
            latest_anime_flow()
        elif act == "b":
            browse_anime_providers()
        elif act == "c":
            continue_anime()
        elif act == "x":
            if FZF.confirm("Clear anime history?"):
                db.clear_history("anime")
                show_success("Cleared")


def search_movies(provider_name: str = "movies"):
    query = show_text_input("Search Movies: ")
    if not query:
        return
    provider = ProviderRegistry.get(provider_name)
    if not provider:
        show_error("Unavailable")
        return

    if isinstance(provider, ChannelProvider):
        status = Status(f"Searching {provider.channel_name}", style="dots")
        status.start()
        try:
            results = provider.search(query)
        except Exception as e:
            status.fail("Failed")
            return
        status.succeed(f"Found {len(results)} results")
        if not results:
            return
        for item in results:
            item["provider"] = provider.name
            item["type"] = "movie"
        sel = show_search_results(results, f"{provider.channel_name}")
        if sel:
            _handle_video_action(sel, "movie")
        return

    lang = show_language_filter()
    if lang == "All languages":
        lang = ""
    sort = {"Latest": "", "Popular": "popular", "Duration: Long to Short": "duration",
            "A-Z": "alpha"}.get(show_sort_options(), "")

    status = Status("Searching Movies", style="dots")
    status.start()
    try:
        results = provider.search(query, language=lang or "", sort=sort)
    except Exception as e:
        status.fail("Failed")
        return
    status.succeed(f"Found {len(results)} results")
    if not results:
        return

    sel = show_search_results(results, "Movies")
    if not sel:
        return

    act = show_action_menu(sel["title"])
    if not act or act == "Back":
        return
    if act == "Copy URL":
        print(sel.get("url", ""))
        return
    if act == "Open in browser":
        open_url(sel.get("url", ""))
        return
    if act == "Play now":
        q = show_quality_menu()
        if q:
            db.add_to_history("movie", sel["title"], sel["url"],
                              provider=sel.get("channel_name", "movies"))
            db.update_movie_progress(sel.get("id", sel["url"]), sel["title"],
                                     0, 0, provider=sel.get("channel_name", "movies"),
                                     url=sel["url"], language=lang or "unknown")
            play_video(sel, q)


def continue_movies() -> None:
    items = db.get_all_movie_progress()
    if not items:
        show_info("No progress")
        return
    lst = [{"title": p["title"], "position": p.get("position", 0),
            "duration": max(p.get("duration", 1), 1),
            "provider": p.get("provider", ""), "url": p.get("url", ""),
            "type": "movie", "id": p.get("id", p.get("movie_id", ""))} for p in items]
    sel = show_continue_menu(lst, "Continue Movies")
    if not sel:
        return
    q = show_quality_menu()
    if q:
        play_video(sel, q, position=sel.get("position", 0))


def browse_movie_providers():
    while True:
        providers = ProviderRegistry.get_channels("movies")
        if not providers:
            show_error("No providers")
            return
        sel = show_provider_list(providers, "Movie Providers")
        if not sel:
            return
        act = show_submenu(sel.channel_name, [
            ("Search in channel", "s"), ("Latest videos", "l"), ("Go Back", "b"),
        ])
        if not act or act == "b":
            continue
        if act == "s":
            search_movies(provider_name=sel.name)
        elif act == "l":
            status = Status(f"Loading {sel.channel_name}", style="dots")
            status.start()
            try:
                results = sel.latest()
            except Exception as e:
                status.fail("Failed")
                show_error(f"Fetch error: {e}")
                log.error(f"Latest [{sel.name}]: {e}")
                continue
            count = len(results)
            status.succeed(f"Found {count} videos" if count else "No videos")
            if not results:
                show_warning(f"{sel.channel_name}: no videos found. "
                             "The channel may be blocked or "
                             "temporarily unavailable.")
                log.warning(f"Latest [{sel.name}]: empty result for "
                            f"{sel.channel_url}")
                continue
            for item in results:
                item["provider"] = sel.name
            chosen = show_search_results(results, f"{sel.channel_name} - Latest")
            if chosen:
                _handle_video_action(chosen, "movie")


def movies_flow() -> None:
    while True:
        act = show_submenu("Movies", [
            ("Search Movies", "s"), ("Latest Movies", "l"),
            ("Browse Movie Providers", "b"),
            ("Continue Movies", "c"),
            ("Clear History", "x"), ("Go Back", "g"),
        ])
        if not act or act == "g":
            break
        if act == "s":
            search_movies()
        elif act == "l":
            latest_movies_flow()
        elif act == "b":
            browse_movie_providers()
        elif act == "c":
            continue_movies()
        elif act == "x":
            if FZF.confirm("Clear movie history?"):
                db.clear_history("movie")
                show_success("Cleared")


def dl_video(item: Dict[str, Any], quality: str = "1080p"):
    url = item.get("url", "")
    if not url:
        return
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in item.get("title", "video"))
    out = Path.home() / "Downloads"
    out.mkdir(parents=True, exist_ok=True)
    dl_quality = quality.replace("audio only", "audio")
    fmt = YTDL_FORMATS.get(dl_quality, YTDL_FORMATS["1080p"])
    title = item.get("title", "video")[:50]
    try:
        proc = subprocess.Popen(
            ["yt-dlp"] + ytdl_cookie_args() + ["--format", fmt, "-o", str(out / f"{safe}.%(ext)s"),
             "--embed-thumbnail", "--embed-metadata",
             "--no-warnings", "--progress", "--newline", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        status = Status(f"[Download] {title}", style="dots")
        status.start()
        for line in proc.stderr:
            parsed = _parse_progress(line)
            if parsed:
                status.update(message=f"[Download] {title} {parsed}", progress=0.0)
        proc.wait()
        if proc.returncode == 0:
            status.succeed(f"[Download] Saved to {out}")
        else:
            status.fail(f"[Download] Failed (exit {proc.returncode})")
    except Exception as e:
        show_error(f"Download failed: {e}")


_preloader: Optional[Preloader] = None


def _get_preloader() -> Preloader:
    global _preloader
    if _preloader is None:
        _preloader = Preloader()
    return _preloader


def play_video(item: Dict[str, Any], quality: str = "720p",
               position: float = 0.0, title: str = ""):
    url = item.get("url", "")
    if not url:
        show_error("No URL")
        return
    video = title or item.get("title", "Video")
    fmt = YTDL_FORMATS.get(quality, YTDL_FORMATS["720p"])
    show_info(f"\u25b6 {video[:60]} [{quality}]")

    db.add_to_history(item.get("type", "video"), video, url,
                      provider=item.get("provider", "youtube"),
                      position=position)

    cache_path = None
    dl_proc = None
    preload_quality = quality.replace("audio only", "audio")

    if preload_quality in PRELOAD_FORMATS:
        pl = _get_preloader()
        cache_result = pl.preload(url, preload_quality, title=video)
        if cache_result is None:
            hint = pl.last_fail_hint
            pl.last_fail_hint = None
            if hint:
                return
        else:
            cache_path, dl_proc = cache_result

    if cache_path:
        cmd = ["mpv", str(cache_path)] + MPV_ARGS
    else:
        cmd = ["mpv", url, f"--ytdl-format={fmt}"] + MPV_ARGS

    watch_later_dir = get_cache_dir() / "watch_later"
    watch_later_dir.mkdir(parents=True, exist_ok=True)
    for f in watch_later_dir.iterdir():
        try:
            f.unlink()
        except OSError:
            pass

    cmd.append(f"--title=hindi-cli - {video[:80]}")
    cmd.append("--save-position-on-quit")
    cmd.append(f"--watch-later-directory={watch_later_dir}")

    if cache_path:
        cmd.append("--cache-pause=no")

    if position > 0:
        cmd.append(f"--start={position}")
    extra = Config().get("player", "mpv_args")
    if isinstance(extra, list):
        cmd.extend(extra)

    proc = None
    exit_pos = 0.0
    try:
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
        proc.wait()
        if proc.returncode == 0:
            show_success(f"Done: {video[:60]}")
        else:
            err = proc.stderr.read()[:200] if proc.stderr else ""
            show_error(f"mpv failed (exit {proc.returncode}): {err.strip()}")
    except FileNotFoundError:
        show_error("mpv not found")
    except Exception as e:
        show_error(f"Error: {e}")
    finally:
        if proc and proc.stderr:
            try:
                proc.stderr.close()
            except OSError:
                pass
        if dl_proc:
            dl_proc.kill()
            dl_proc.wait()
        if cache_path:
            Preloader._cleanup_file(cache_path)

    for f in watch_later_dir.iterdir():
        try:
            text = f.read_text()
            for line in text.splitlines():
                if line.startswith("start="):
                    val = line.split("=", 1)[1].strip()
                    exit_pos = float(val)
                    break
        except (OSError, ValueError):
            pass
        try:
            f.unlink()
        except OSError:
            pass

    if exit_pos > 5:
        media_type = item.get("type") or item.get("media_type", "video")
        db.update_history_position(url, exit_pos)
        if media_type == "anime":
            aid = item.get("anime_id") or item.get("id", "") or video.replace(" ", "_").lower()
            db.update_playback_position("anime", aid, video,
                                          exit_pos, item.get("duration", 0),
                                          provider=item.get("provider", "anime"),
                                          url=url)
        elif media_type == "movie":
            mid = item.get("id", url)
            db.update_playback_position("movie", mid, video,
                                          exit_pos, item.get("duration", 0),
                                          provider=item.get("provider", "movies"),
                                          url=url)


def main_loop(args: argparse.Namespace):
    check_deps()
    signal.signal(signal.SIGTERM, sig_handler)

    if not args.quiet:
        _splash()

    while True:
        choice = show_main_menu()
        if choice is None or choice == "Quit":
            show_info("Bye!")
            break
        {
            "YouTube": yt_flow,
            "Anime": anime_flow,
            "Movies": movies_flow,
        }.get(choice, lambda: None)()
        if not args.quiet:
            _splash()


COOKIES_PATH = Path.home() / ".config" / "hindi-cli" / "cookies.txt"


def _login() -> None:
    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_PATH.unlink(missing_ok=True)
    print()
    print(f"  \u2699 YouTube Login")
    print(f"  {'─' * 50}")
    print(f"  First, sign into YouTube in your browser.")
    print(f"  Then leave the browser open and run this again.")
    print()

    browsers = ["firefox", "chrome", "chromium", "brave", "edge", "opera", "vivaldi"]
    cookie_dirs = {
        "firefox": Path.home() / ".mozilla" / "firefox",
        "chrome": Path.home() / ".config" / "google-chrome",
        "chromium": Path.home() / ".config" / "chromium",
        "brave": Path.home() / ".config" / "BraveSoftware" / "Brave-Browser",
        "edge": Path.home() / ".config" / "microsoft-edge",
        "opera": Path.home() / ".config" / "opera",
        "vivaldi": Path.home() / ".config" / "vivaldi",
    }
    found = None
    for browser in browsers:
        d = cookie_dirs.get(browser)
        if not (d and d.exists() and any(d.iterdir())):
            continue
        print(f"  {browser}...", end=" ")
        COOKIES_PATH.unlink(missing_ok=True)
        try:
            r = subprocess.run(
                ["yt-dlp", "--cookies-from-browser", browser, "--cookies", str(COOKIES_PATH),
                 "--skip-download", "--print", "title",
                 "https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
                capture_output=True, text=True, timeout=30,
            )
            has_auth = r.returncode == 0
        except Exception:
            has_auth = False
        if not has_auth and COOKIES_PATH.exists() and COOKIES_PATH.stat().st_size > 100:
            raw = COOKIES_PATH.read_text()
            if "SAPISID" in raw or "__Secure-3PAPISID" in raw:
                has_auth = True
        if has_auth:
            print("\u2713 cookies saved")
            found = browser
            break
        print("\u2717 no YouTube login found")

    if found:
        show_success(f"Cookies saved from {browser}")
        Config().set(str(COOKIES_PATH), "youtube", "cookies_file")
    else:
        show_error("No browser with YouTube login found.")
        print()
        print("  To fix:")
        print("  1. Open Firefox and go to https://accounts.google.com")
        print("  2. Sign in with any Google account")
        print("  3. Keep the browser open")
        print("  4. Run: hindi-cli --login")
        if COOKIES_PATH.exists():
            COOKIES_PATH.unlink()
    print()


def _logout() -> None:
    if COOKIES_PATH.exists():
        COOKIES_PATH.unlink()
        show_success("Cookies cleared")
    cfg_path = str(COOKIES_PATH)
    if Config().get("youtube", "cookies_file") == cfg_path:
        Config().set("", "youtube", "cookies_file")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="hindi-cli",
        description="Terminal streaming utility — YouTube, Anime, and Movies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hindi-cli                  Start interactive mode
  hindi-cli --doctor         Check system health
  hindi-cli --stats          Show usage statistics
  hindi-cli --history        Show watch history
  hindi-cli --clear-cache    Clear all cached data
  hindi-cli --version        Show version
        """,
    )

    parser.add_argument("--version", action="store_true",
                        help="Show version and exit")
    parser.add_argument("--about", action="store_true",
                        help="Show about information")
    parser.add_argument("--doctor", action="store_true",
                        help="Run system diagnostics")
    parser.add_argument("--stats", action="store_true",
                        help="Show usage statistics")
    parser.add_argument("--history", action="store_true",
                        help="Show watch history")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Clear all cached data")
    parser.add_argument("--config", action="store_true",
                        help="Show config file path and contents")
    parser.add_argument("--check-update", action="store_true",
                        help="Check for updates")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose output")
    parser.add_argument("--no-cache", action="store_true",
                        help="Disable caching")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress startup banner")
    parser.add_argument("--player", type=str, default=None,
                        choices=["mpv", "vlc"],
                        help="Set default player (mpv or vlc)")
    parser.add_argument("--login", action="store_true",
                        help="Save YouTube cookies from your browser for authentication")
    parser.add_argument("--logout", action="store_true",
                        help="Clear saved YouTube cookies")

    args = parser.parse_args()

    if args.verbose or args.debug:
        setup_logger("DEBUG")

    if args.player:
        Config().set(args.player, "player", "default")
        show_info(f"Default player set to {args.player}")

    if args.no_cache:
        Config().set(False, "preload", "enabled")

    if args.version:
        print(version_string())
        return
    if args.about:
        print(about_string())
        return
    if args.doctor:
        _doctor()
        return
    if args.stats:
        _show_stats()
        return
    if args.history:
        _show_history()
        return
    if args.clear_cache:
        _clear_cache()
        return
    if args.config:
        _show_config()
        return
    if args.check_update:
        _check_update()
        return

    Preloader.cleanup_stale()
    try:
        if args.login:
            _login()
            return
        if args.logout:
            _logout()
            return
        main_loop(args)
    except KeyboardInterrupt:
        print()
    except Exception as e:
        log.error(f"Fatal: {e}", exc_info=True)
        show_error(str(e))
        sys.exit(1)
    finally:
        Preloader.cleanup_all()
        db.close()


if __name__ == "__main__":
    main()
