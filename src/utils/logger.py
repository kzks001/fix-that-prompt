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

    # Create logs directory if it doesn't exist (for local development)
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

    # Check if running in AWS environment
    is_aws = bool(
        os.getenv("AWS_REGION")
        or os.getenv("ECS_CONTAINER_METADATA_URI")
        or os.getenv("AWS_EXECUTION_ENV")
    )

    if is_aws:
        # In AWS, logs go to CloudWatch via ECS log driver
        # No additional file logging needed
        logger.info("Running in AWS environment - logs will be sent to CloudWatch")
    else:
        # Local development - file logging
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


def get_dynamodb_logger():
    """Get a logger configured for DynamoDB operations."""
    return logger.bind(DYNAMODB_OP=True)


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


def log_dynamodb_operation(
    operation: str,
    table: str,
    username: str = None,
    success: bool = True,
    error: str = None,
) -> None:
    """
    Log DynamoDB operations for monitoring and debugging.

    Args:
        operation: The DynamoDB operation (e.g., 'get_item', 'put_item', 'query')
        table: The DynamoDB table name
        username: The username being operated on (if applicable)
        success: Whether the operation was successful
        error: Error message if operation failed
    """
    dynamodb_logger = get_dynamodb_logger()

    if success:
        dynamodb_logger.info(
            f"DynamoDB operation - Table: {table}, Operation: {operation}, "
            f"Username: {username or 'N/A'}, Status: SUCCESS"
        )
    else:
        dynamodb_logger.error(
            f"DynamoDB operation - Table: {table}, Operation: {operation}, "
            f"Username: {username or 'N/A'}, Status: FAILED, Error: {error}"
        )


def log_dynamodb_error(
    operation: str, table: str, username: str = None, error: Exception = None
) -> None:
    """
    Log DynamoDB errors specifically for monitoring.

    Args:
        operation: The DynamoDB operation that failed
        table: The DynamoDB table name
        username: The username being operated on (if applicable)
        error: The exception that occurred
    """
    dynamodb_logger = get_dynamodb_logger()
    error_msg = str(error) if error else "Unknown error"

    dynamodb_logger.error(
        f"DynamoDB ERROR - Table: {table}, Operation: {operation}, "
        f"Username: {username or 'N/A'}, Error: {error_msg}"
    )

    # Also log to general error logger for CloudWatch alarms
    logger.error(
        f"DynamoDB operation failed - Table: {table}, Operation: {operation}, "
        f"Username: {username or 'N/A'}, Error: {error_msg}"
    )
