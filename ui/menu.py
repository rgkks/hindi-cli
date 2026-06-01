from typing import Dict, List, Optional, Tuple

from core.fzf import FZF


def _header(text: str) -> str:
    return f"┌─ {text} {'─' * max(0, 50 - len(text))}┐\n│  /: search, Esc: back                    │\n└{'─'*55}┘"


def show_main_menu() -> Optional[str]:
    result = FZF.menu(["YouTube", "Anime", "Movies", "Quit"],
                      prompt="hindi-cli > ", header=_header("Select category"))
    return "Quit" if result is None else result


def show_submenu(title: str, items: List[Tuple[str, str]]) -> Optional[str]:
    labels = [i[0] for i in items]
    result = FZF.menu(labels, prompt=f"{title} > ", header=_header(title))
    if result is None:
        return None
    for label, value in items:
        if result == label:
            return value
    return result


def show_search_results(items: List[Dict], title: str = "Results") -> Optional[Dict]:
    if not items:
        return None
    labels = [i.get("label", i.get("title", "")) for i in items]
    result = FZF.menu(labels, prompt=f"{title} > ", header=_header(title))
    if result is None:
        return None
    for item in items:
        if result == item.get("label", item.get("title", "")):
            return item
    return None


def show_provider_list(providers: Dict[str, object], title: str = "Providers") -> Optional[object]:
    if not providers:
        return None
    labels = [f"{p.channel_name}  ({', '.join(p.languages)})" for p in providers.values()]
    result = FZF.menu(labels, prompt=f"{title} > ", header=_header(title))
    if result is None:
        return None
    for name, p in providers.items():
        label = f"{p.channel_name}  ({', '.join(p.languages)})"
        if result == label:
            return p
    return None


def show_quality_menu() -> Optional[str]:
    return FZF.menu(
        ["720p", "480p", "360p", "1080p", "1440p", "2160p", "audio only"],
        prompt="Quality > ", header=_header("Video quality (720p recommended)")
    )


def show_action_menu(video_title: str) -> Optional[str]:
    actions = ["▶  Play now", "⬇  Download", "📋  Copy URL",
               "🌐  Open in browser", "❤  Like", "◀  Back"]
    result = FZF.menu(actions, prompt="Action > ", header=_header(video_title[:50]))
    if result:
        for a in actions:
            if result == a:
                parts = a.split("  ", 1)
                return parts[-1] if len(parts) > 1 else parts[0]
    return None


def show_language_filter() -> Optional[str]:
    return FZF.menu(
        ["All languages", "Hindi", "English", "Tamil", "Telugu",
         "Malayalam", "Kannada", "Bengali", "Japanese", "Korean"],
        prompt="Language > ", header=_header("Filter language")
    )


def show_sort_options() -> Optional[str]:
    return FZF.menu(
        ["Latest", "Popular", "Duration: Long to Short", "A-Z"],
        prompt="Sort by > ", header=_header("Sort options")
    )


def show_time_filter() -> Optional[str]:
    return FZF.menu(
        ["All time", "Last 24 hours", "Last 7 days", "Last 30 days"],
        prompt="Time > ", header=_header("Time filter")
    )


def show_continue_menu(items: List[Dict], title: str = "Continue") -> Optional[Dict]:
    if not items:
        return None
    labels = []
    for item in items:
        dur = max(item.get("duration", 1), 1)
        pct = int((item.get("position", 0) / dur) * 100)
        labels.append(f"{item['title']} [{pct}%] - {item.get('provider', '?')}")
    result = FZF.menu(labels, prompt=f"{title} > ", header=_header(title))
    if result is None:
        return None
    for i, item in enumerate(items):
        dur = max(item.get("duration", 1), 1)
        pct = int((item.get("position", 0) / dur) * 100)
        label = f"{item['title']} [{pct}%] - {item.get('provider', '?')}"
        if result == label:
            return item
    return None


def show_text_input(prompt_text: str = "Search: ") -> Optional[str]:
    try:
        result = input(f"\033[1;36m{prompt_text}\033[0m")
        return result.strip() or None
    except (KeyboardInterrupt, EOFError):
        return None


def show_error(message: str):
    print(f"\033[1;31m✗ {message}\033[0m")


def show_success(message: str):
    print(f"\033[1;32m✓ {message}\033[0m")


def show_info(message: str):
    print(f"\033[1;34mℹ {message}\033[0m")


def show_warning(message: str):
    print(f"\033[1;33m⚠ {message}\033[0m")
