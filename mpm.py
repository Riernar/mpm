# Standard lib import
import argparse
import logging
from pathlib import Path

# Local imports
import mc_pack_manager as mpm

LOGGER = logging.getLogger(__name__)

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minecraft Pack Manager -- Helps managae minecraft modpacks")
    subparsers = parser.add_subparsers(dest="command", required=True, help="subcommands help")

    # Snapshot subcommand
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="snapshot help"
    )
    snapshot_parser.description = "Creates more advanced modpack representation on top of curse representation"
    snapshot_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Local dir in which to build or update the modpack representation"
    )
    snapshot_parser.add_argument(
        "curse_zip",
        type=Path,
        help="path to the zip file exported by curse/twitch app"
    )

    # Argument parsing
    args = parser.parse_args()
    print(args)

    # Logging config
    configure_logging()

    # Command selection
    try:
        if args.command == "snapshot":
            mpm.manager.snapshot(
                pack_dir=args.pack_dir,
                curse_zip=args.curse_zip
            )
    
    except Exception as err:
        LOGGER.exception(
            "Minecraft Pack Manager encountered an exception:\n%s", mpm.utils.err_str(err)
        )
        print(
            "An exception occured, see above. Exceptions are not yet handled in MPM, so this might be because of wrong argument.\n"
            "The exception is: %s" % mpm.utils.err_str(err)
        )

