"""Настройка loguru; вызывается один раз из create_app."""

import sys

from loguru import logger

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "{extra[request_id]} | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def setup_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    logger.remove()
    # request_id проставится request-middleware (шаг 5); до тех пор — прочерк.
    logger.configure(extra={"request_id": "-"})
    if json_logs:
        logger.add(sys.stderr, level=level, serialize=True)
    else:
        logger.add(sys.stderr, level=level, format=_CONSOLE_FORMAT)
