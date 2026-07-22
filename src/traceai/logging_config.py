"""Structured JSON logging configuration for TraceAI."""

import json
import logging
import logging.config
from datetime import datetime, timezone
from pathlib import Path

import yaml

from traceai.settings import get_project_root


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging from config/logging.yaml or fall back to basic config."""
    root = get_project_root()
    config_path = root / "config" / "logging.yaml"

    # Ensure log directory exists
    log_dir = root / "workspace"
    log_dir.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        # Fix relative log file path
        if "handlers" in config and "file" in config["handlers"]:
            log_file = root / config["handlers"]["file"]["filename"]
            log_file.parent.mkdir(parents=True, exist_ok=True)
            config["handlers"]["file"]["filename"] = str(log_file)
        try:
            logging.config.dictConfig(config)
        except Exception:
            _basic_config(level)
    else:
        _basic_config(level)


def _basic_config(level: str) -> None:
    """Fallback basic logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    """Get a named logger for TraceAI modules."""
    return logging.getLogger(f"traceai.{name}")
