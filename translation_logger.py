import logging
import os
from datetime import datetime
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


def _ensure_log_dir(log_dir: Path) -> None:
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)


def get_logger(name: str = "doc_translation") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        # Already configured
        return logger

    logger.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(ch)

    # File handler (daily log file)
    log_dir = Path("logs")
    _ensure_log_dir(log_dir)
    today_str = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"doc_translation_{today_str}.log"

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(fh)

    logger.propagate = False
    return logger


logger = get_logger()
