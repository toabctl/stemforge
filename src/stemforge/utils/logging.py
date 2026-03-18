"""Logging configuration for stemforge."""

import logging
import sys


def configure_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Set up a clean, human-readable log format on stderr."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Silence noisy third-party loggers at DEBUG level
    for name in ("spotipy", "urllib3", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
