from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from typing import Optional

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(value: str) -> None:
    _REQUEST_ID.set(value)


def get_request_id() -> str:
    return _REQUEST_ID.get()


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def setup_logging(level: Optional[str] = None) -> None:
    log_level = level or os.getenv("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
    )
    root = logging.getLogger()
    root.addFilter(RequestIdFilter())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
