from __future__ import annotations

import logging
import sys

LOG_FORMAT = "%(asctime)s │ %(name)-28s │ %(levelname)-7s │ %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: int = logging.WARNING) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root = logging.getLogger("github_scrape")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"github_scrape.{name}")
