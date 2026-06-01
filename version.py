"""Centralized version management for hindi-cli."""

__version__ = "Beta 1.38.4"
__release__ = "1.38.4"
__codename__ = "Terminal Stream"
__author__ = "hindi-cli"
__license__ = "MIT"
__description__ = "Terminal streaming utility — YouTube, Anime, and Movies"
__url__ = "https://github.com/rgkks/hindi-cli"


def version_string() -> str:
    return f"hindi-cli {__version__}"


def about_string() -> str:
    return (
        f"hindi-cli {__version__}\n"
        f"{__description__}\n"
        f"License: {__license__}\n"
        f"URL: {__url__}"
    )
