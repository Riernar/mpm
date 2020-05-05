#!/usr/bin/env python
"""
Command-line interface for MPM

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard lib import
import argparse
import inspect
import logging
from pathlib import Path
import traceback

# Local imports
import mc_pack_manager as mpm

MPM_FILE = Path(inspect.getfile(inspect.currentframe())).absolute()

LOGGER = logging.getLogger("mpm")

FILE_FORMAT = "[{asctime}][{name: <20}][{funcName}()][{levelname}] {message}"
CONSOLE_FORMAT = "[{levelname}] {message}"
CONSOLE_FORMAT_DEBUG = "[{name: <20}][{levelname}] {message}"


def configure_logging(debug=False, log_file: Path = "mc-pack-manager.log"):
    # module logger
    logger = logging.getLogger("mpm")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    # Logging to file
    ## Handler
    file_handler = logging.FileHandler(str(log_file), mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    ## Formatyer
    file_formatter = logging.Formatter(FILE_FORMAT, style="{")
    file_handler.setFormatter(file_formatter)
    # Console logging
    ## Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    ## Formatter
    console_formatter = logging.Formatter(
        CONSOLE_FORMAT_DEBUG if debug else CONSOLE_FORMAT, style="{"
    )
    console_handler.setFormatter(console_formatter)
    # Attach to module logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Minecraft Pack Manager -- Helps manage minecraft modpacks"
    )
    parser.add_argument(
        "-d", "--debug", help="Activate debug mode on the console", action="store_true"
    )
    parser.add_argument(
        "-l",
        "--logdir",
        type=Path,
        help="Path to the directory to write the log into. If a file is provided, its parent is used",
    )
    subparsers = parser.add_subparsers(required=True, help="Available subcommands:")

    # Snapshot subcommand
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Creates a snapshot from a curse-generated zip. Snapshots are an improved version of curse's modpack zip",
    )
    snapshot_parser.description = (
        "Creates or updates a snapshot zip from the provided curse modpack zip"
    )
    snapshot_parser.set_defaults(command=mpm.manager.snapshot.snapshot)
    snapshot_parser.add_argument(
        "curse_zip",
        type=Path,
        help="path to the zip file exported by the curse/twitch app",
    )
    snapshot_parser.add_argument(
        "snapshot", type=Path, help="path to the snapshot file to create or update",
    )
    snapshot_parser.add_argument(
        "-v",
        "--version-incr",
        choices=("MINOR", "MEDIUM", "MAJOR"),
        default="MINOR",
        help="Version number of the snapshot to increase. Defaults to MINOR",
    )
    snapshot_parser.add_argument(
        "--include-mpm",
        action="store_true",
        help="Bundle MPM into the snapshot as an override. This is useful when client update from an http server and you want to update MPM with the pack (you still need to use --include-mpm to bundle it in the release)",
    )

    # Release subcommands
    release_parser = subparsers.add_parser(
        "release",
        help="Creates a curse modpack zip or server files from a MPM snapshot",
    )
    release_parser.description = (
        "Creates a curse modpack zip or server files from a MPM snapshot"
    )
    release_subparser = release_parser.add_subparsers(
        required=True, help="Release type"
    )
    ## Curse release
    curse_release_parser = release_subparser.add_parser(
        "curse",
        help="Makes a curse modpack zip. Used to release a pack version for Curse or MultiMC",
    )
    curse_release_parser.description = "Creates a release .zip of the modpack compatible with curse, the twitch app and MultiMC. Allows to select packmodes to release"
    curse_release_parser.set_defaults(command=mpm.manager.release.curse)
    curse_release_parser.add_argument(
        "snapshot",
        type=Path,
        help="Path to the snapshot file generated by 'mpm snapshot'",
    )
    curse_release_parser.add_argument(
        "output_zip", type=Path, help="Path to the zip file to create"
    )
    curse_release_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite the output zip if it already exists",
    )
    curse_release_parser.add_argument(
        "--include-mpm",
        action="store_true",
        help="Bundle MPM into the release, ready to use for auto-updates",
    )
    curse_release_parser.add_argument(
        "packmodes",
        metavar="packmode",
        nargs="*",
        help="Packmodes to export to the release. MPM will only include mods and overrides belonging to those packmodes or their dependencies. Defaults to all packmodes",
        default=[],
    )
    ## Server release
    server_release_parser = release_subparser.add_parser(
        "serverfiles",
        help="Creates server files, with mod jars and overrides. Doesn't include minecraft or minecraftforge",
    )
    server_release_parser.description = "Creates the server files for the selected packmodes, with mods' jar and overrides. Be mindfule of mods' licence before ditributing this. WARNING: this does *not* contains minecraft or minecraftforge"
    server_release_parser.set_defaults(command=mpm.manager.release.serverfiles)
    server_release_parser.add_argument(
        "snapshot",
        type=Path,
        help="Path to the snapshot file generated with 'mpm snapshot'",
    )
    server_release_parser.add_argument(
        "output_zip", type=Path, help="Path to the zip file to create"
    )
    server_release_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite the output zip if it already exists",
    )
    server_release_parser.add_argument(
        "--include-mpm",
        action="store_true",
        help="Bundle MPM into the release, ready tor use fo auto-updates",
    )
    server_release_parser.add_argument(
        "packmodes",
        metavar="packmode",
        nargs="*",
        help="Packmodes to export to the release. MPM will only include mods and overrides belonging to those packmodes or their dependencies. Defaults to 'server'",
        default=[],
    )

    # Update subcommand
    update_parser = subparsers.add_parser(
        "update", help="Updates a modpack installation from a MPM snapshot",
    )
    update_parser.description = (
        "Updates a modpack installation to a different version and/or set of packmodes"
    )
    update_parser.set_defaults(command=mpm.manager.update.update)
    update_parser.epilog = (
        "NOTE: Changing packmodes without changing versions is fully supported"
    )
    update_parser.add_argument(
        "source", help="Update source, by default a path. See also --update"
    )
    update_parser.add_argument(
        "install", help="Installation path or url, by default a path. See also --pack"
    )
    update_parser.add_argument(
        "-u",
        "--update",
        choices=("local", "http"),
        default="local",
        dest="source_type",
        help="Specifies the type of the update source. Defaults to 'local'. LOCAL: path to a local MPM snapshot file. HTTP: url to a http(s) server exposing the content of the MPM snapshot",
    )
    update_parser.add_argument(
        "-i",
        "--install",
        choices=("local", "ftp"),
        default="local",
        dest="install_type",
        help="Specifies the type of the pack installation. Defaults to 'local'. LOCAL: ath to a local modpack directory. FTP: ftp url to a remote modpack installtion, e.g. a hosted minecraft server",
    )
    update_parser.add_argument(
        "packmodes",
        metavar="packmode",
        nargs="*",
        help="Packmodes to update to. MPM will only install mods and overrides belonging to those packmodes and their dependencies, and remove others mods and overrides it knows of",
        default=[],
    )

    # Argument parsing
    args = parser.parse_args()
    kwargs = vars(args)
    if "include_mpm" in kwargs:
        kwargs["mpm_filepath"] = MPM_FILE if kwargs.pop("include_mpm") else None

    # Logging configuration
    logdir = kwargs.pop("logdir", Path("."))
    if logdir.is_file():
        logdir = logdir.parent
    if not logdir.is_dir():
        parser.error("%s is not a directory" % logdir)
    configure_logging(
        debug=kwargs.pop("debug", False), log_file=logdir / "mc-pack-manager.log"
    )

    # Command selection
    try:
        command = kwargs.pop("command")
        command(**kwargs)
    except Exception as err:
        LOGGER.error(
            "Minecraft Pack Manager encountered an exception:\n\n%s",
            mpm.utils.err_str(err),
        )
        LOGGER.debug(
            "Detailed statcktrace:\n%s", "".join(traceback.format_tb(err.__traceback__))
        )
        print(
            "An exception occured, see above. The full stacktrace is available in the log file."
            " Exceptions are not yet handled in MPM, so this might be because of a wrong argument.\n"
            "If this is a problem in MPM, please fill in an issue at\nhttps://github.com/Riernar/mpm/issues\nand provide the log file"
        )
