# Standard lib import
import argparse
import logging
from pathlib import Path

# Local imports
import mc_pack_manager as mpm


FILE_FORMAT = "[{asctime}][{name}][{funcName}][{levelname}] {message}"
CONSOLE_FORMAT = "[{name}][{levelname}] {message}"


def configure_logging(log_file: Path = "mc-pack-manager.log"):
    # module logger
    logger = logging.getLogger("mpm")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    # Logging to file
    ## Handler
    file_handler = logging.FileHandler(str(log_file))
    file_handler.setLevel(logging.DEBUG)
    ## Formatyer
    file_formatter = logging.Formatter(FILE_FORMAT, style="{")
    file_handler.setFormatter(file_formatter)
    # Console logging
    ## Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    ## Formatter
    console_formatter = logging.Formatter(CONSOLE_FORMAT, style="{")
    console_handler.setFormatter(console_formatter)
    # Attach to module logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
