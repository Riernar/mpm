# Standard lib import
import argparse
import logging
from pathlib import Path

# Local imports
import mc_pack_manager as mpm

LOGGER = logging.getLogger("mpm")

FILE_FORMAT = "[{asctime}][{name}][{funcName}()][{levelname}] {message}"
CONSOLE_FORMAT = "[{name}][{levelname}] {message}"


def configure_logging(log_file: Path = "mc-pack-manager.log"):
    # module logger
    logger = logging.getLogger("mpm")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    # Logging to file
    ## Handler
    file_handler = logging.FileHandler(str(log_file), mode="w")
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
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Minecraft Pack Manager -- Helps manage minecraft modpacks"
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="subcommands help"
    )

    # Snapshot subcommand
    snapshot_parser = subparsers.add_parser("snapshot", help="snapshot help")
    snapshot_parser.description = (
        "Creates or updates a snapshot of the curse pack into pack_dir"
    )
    snapshot_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Local dir in which to build or update the modpack representation",
    )
    snapshot_parser.add_argument(
        "curse_zip", type=Path, help="path to the zip file exported by curse/twitch app"
    )
    # Release subcommands
    release_parser = subparsers.add_parser("release", help="release help")
    release_parser.description = "Creates .zip file for various release format"
    release_subparser = release_parser.add_subparsers(
        dest="release_type", required=True, help="Specific release type"
    )
    ## MPM Release subcommand
    mpm_release_parser = release_subparser.add_parser("mpm", help="Release compatible with mpm")
    mpm_release_parser.description = "Creates a release .zip compatible with mpm - simply the compressed snapshot"
    mpm_release_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Snapshot directory were the snapshot was generated using 'mpm snapshot'"
    )
    mpm_release_parser.add_argument(
        "output_zip",
        type=Path,
        help="Path to the zipfile to create"
    )
    mpm_release_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="erase output_zip if it already exists"
    )
    ## Curse release
    curse_release_parser = release_subparser.add_parser("curse", help="Release compatible with curse")
    curse_release_parser.description = "Creates a release .zip compatible with curse and the twitch app"
    curse_release_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Snapshot directory were the snapshot was generated using 'mpm snapshot'"
    )
    curse_release_parser.add_argument(
        "output_zip",
        type=Path,
        help="Path to the zipfile to create"
    )
    curse_release_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="erase output_zip if it already exists"
    )
    curse_release_parser.add_argument(
        "--include-mpm",
        action="store_true",
        help="Bundle mpm (Minecraft Pack Manager) into the release, ready to use fo auto-updates"
    )
    curse_release_parser.add_argument(
        "packmodes",
        metavar="packmode",
        nargs="*",
        help="Only include mods/overrides belonging to those packmodes and their dependencies",
        default=[]
    )

    # Argument parsing
    args = parser.parse_args()

    # Command selection
    try:
        if args.command == "snapshot":
            mpm.manager.snapshot(pack_dir=args.pack_dir, curse_zip=args.curse_zip)
        elif args.command == "release":
            if args.release_type == "mpm":
                mpm.manager.release_mpm(pack_dir=args.pack_dir, output_file=args.output_zip, force=args.force)
            elif args.release_type == "curse":
                mpm.manager.release_curse(
                    pack_dir=args.pack_dir,
                    output_zip=args.output_zip,
                    packmodes=args.packmodes,
                    force=args.force,
                    include_mpm=args.include_mpm
                )

    except Exception as err:
        LOGGER.exception(
            "Minecraft Pack Manager encountered an exception:\n%s",
            mpm.utils.err_str(err),
        )
        print(
            "\n\n"
            + "An exception occured, see above. Exceptions are not yet handled in MPM, so this might be because of a wrong argument.\n"
            + ("The exception is: %s" % mpm.utils.err_str(err))
            + "If this is a problem in MPM, please fill in an issue at https://github.com/Riernar/mpm/issues"
        )
