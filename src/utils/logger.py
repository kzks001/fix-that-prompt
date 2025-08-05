"""Logging configuration and utilities using Loguru."""

import os
import sys
from pathlib import Path
from loguru import logger


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure loguru logging for the application.

    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Remove default logger
    logger.remove()

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Console logging with colors
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level=log_level,
        colorize=True,
    )

    # File logging - general logs
    logger.add(
        log_dir / "fix_that_prompt.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        level=log_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )

    # File logging - game events only
    logger.add(
        log_dir / "game_events.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        level="INFO",
        filter=lambda record: "GAME_EVENT" in record["extra"],
        rotation="5 MB",
        retention="30 days",
        compression="zip",
    )

    # File logging - errors only
    logger.add(
        log_dir / "errors.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}"
        ),
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
    )


def get_game_logger():
    """Get a logger configured for game events."""
    return logger.bind(GAME_EVENT=True)


def log_player_action(username: str, action: str, details: str = "") -> None:
    """
    Log a player action for game tracking.

    Args:
        username: The player's username
        action: The action taken (e.g., 'started_game', 'submitted_prompt')
        details: Additional details about the action
    """
    game_logger = get_game_logger()
    game_logger.info(
        f"Player action - Username: {username}, Action: {action}, "
        f"Details: {details}"
    )


def log_game_event(event_type: str, data: dict) -> None:
    """
    Log a general game event.

    Args:
        event_type: Type of event (e.g., 'round_completed', 'game_ended')
        data: Dictionary containing event data
    """
    game_logger = get_game_logger()
    game_logger.info(f"Game event - Type: {event_type}, Data: {data}")


def log_score_event(username: str, round_num: int, score: float) -> None:
    """
    Log a scoring event.

    Args:
        username: The player's username
        round_num: The round number
        score: The RAGAS score achieved
    """
    game_logger = get_game_logger()
    game_logger.info(
        f"Score event - Username: {username}, Round: {round_num}, "
        f"Score: {score:.2f}"
    )
