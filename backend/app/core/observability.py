"""Bounded per-request stage timings, with no global metric history."""

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

stages: ContextVar[dict[str, float] | None] = ContextVar("request_stages", default=None)
logger = logging.getLogger("adflow.requests")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(record.__dict__["request_context"], sort_keys=True)


def configure_logging(level: str) -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


@contextmanager
def stage(name: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        timings = stages.get()
        if timings is not None:
            timings[name] = timings.get(name, 0.0) + (perf_counter() - started) * 1000
