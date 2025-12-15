"""Twitter Voice Agent - CLI tool for analyzing Twitter voices and generating content."""

from loguru import logger

__version__ = "0.1.0"

# Configure loguru logging - use structured logging for internal operations
# Console output for user-facing messages is handled by rich in cli.py
logger.remove()  # Remove default handler
logger.add(
    lambda msg: print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO",
    colorize=True,
)
