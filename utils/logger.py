import logging
import sys
from pathlib import Path

from utils.platform import get_cache_dir


LOG_DIR = get_cache_dir()
LOG_PATH = LOG_DIR / "hindi-cli.log"


def setup_logger(level: str = "INFO") -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("hindi-cli")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fh = logging.FileHandler(str(LOG_PATH))
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(getattr(logging, level.upper(), logging.WARNING))
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


log = setup_logger()
