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
CONSOLE_FORMAT = "[{name: <20}][{levelname}] {message}"


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
        dest="command", required=True, help="Available subcommands:"
    )

    # Snapshot subcommand
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Creates a snapshot, an enriched representation of a modpack, from a curse-generated zip",
    )
    snapshot_parser.description = (
        "Creates or updates a snapshot of the curse pack into pack_dir"
    )
    snapshot_parser.add_argument(
        "curse_zip",
        type=Path,
        help="path to the zip file exported by the curse/twitch app",
    )
    snapshot_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Local dir in which to build or update the modpack representation",
    )

    # Release subcommands
    release_parser = subparsers.add_parser(
        "release",
        help="make various zip, used for releasing the pack, from snapshots (see 'mpm snapshot')",
    )
    release_parser.description = "Creates zip file for various release format"
    release_subparser = release_parser.add_subparsers(
        dest="release_type", required=True, help="Specific release type"
    )
    ## MPM Release subcommand
    mpm_release_parser = release_subparser.add_parser(
        "mpm", help="Release containing the full snapshot. Used for updating with MPM"
    )
    mpm_release_parser.description = "Creates a release zip compatible with MPM, used for updating with MPM (see 'mpm update')"
    mpm_release_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Snapshot directory where the snapshot was generated using 'mpm snapshot'",
    )
    mpm_release_parser.add_argument(
        "output_zip", type=Path, help="Path to the zip file to create"
    )
    mpm_release_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite the output zip if it already exists",
    )
    ## Curse release
    curse_release_parser = release_subparser.add_parser(
        "curse",
        help="Release compatible with curse. Used to a set of packmodes as a standard curse modpack",
    )
    curse_release_parser.description = (
        "Creates a release .zip compatible with curse and the twitch app"
    )
    curse_release_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Snapshot directory were the snapshot was generated using 'mpm snapshot'",
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
        help="Bundle MPM into the release, ready to use fo auto-updates",
    )
    curse_release_parser.add_argument(
        "packmodes",
        metavar="packmode",
        nargs="*",
        help="Packmodes to export to the release. MPM will only include mods and overrides belonging to those packmodes or packmodes they depend on. Defaults to all packmodes",
        default=[],
    )
    ## Server release
    server_release_parser = release_subparser.add_parser(
        "serverfiles", help="Release ready for a server with mods jars and overrides"
    )
    server_release_parser.description = "Release containing all files necessary to run the selected packmodes. Contains mod JAR file ! Be mindfule of mod licences before ditributing the release ! WARNING: this does *not* contains forge or minecraft"
    server_release_parser.add_argument(
        "pack_dir",
        type=Path,
        help="Snapshot directory were the snapshot was generated using 'mpm snapshot'",
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
        help="Bundle MPM into the release, ready to use fo auto-updates",
    )
    server_release_parser.add_argument(
        "packmodes",
        metavar="packmode",
        nargs="*",
        help="Packmodes to export to the release. MPM will only include mods and overrides belonging to those packmodes or packmodes they depend on. Defaults to 'server'",
        default=[],
    )

    # Update subcommand
    update_parser = subparsers.add_parser(
        "update",
        help="updates a modpack dir from an mpm release (see 'mpm release mpm')",
    )
    update_parser.description = (
        "Updates a pack installation to a different version and/or set of packmodes"
    )
    install_group = update_parser.add_mutually_exclusive_group(required=True)
    install_group.add_argument(
        "--pack-local",
        type=Path,
        metavar="PATH",
        help="Path to the local installation directory to update (./minecraft dir)",
    )
    install_group.add_argument(
        "--pack-ftp",
        metavar="URL",
        help="FTP url to a remote installation to update, pointing to the remote ./minecraft directory",
    )
    update_group = update_parser.add_mutually_exclusive_group(required=True)
    update_group.add_argument(
        "--update-zip",
        metavar="PATH",
        type=Path,
        help="Path to a local .zip generated by 'mpm release mpm'",
    )
    update_group.add_argument(
        "--update-http",
        metavar="URL",
        help="HTTP(S) url to a server exposing the content of an mpm release generated by 'mpm release mpm' (e.g. github repo, webserver ...)",
    )

    # Argument parsing
    args = parser.parse_args()

    # Command selection
    try:
        if args.command == "snapshot":
            mpm.manager.snapshot.snapshot(
                pack_dir=args.pack_dir, curse_zip=args.curse_zip
            )
        elif args.command == "release":
            if args.release_type == "mpm":
                mpm.manager.release.mpm(
                    pack_dir=args.pack_dir,
                    output_file=args.output_zip,
                    force=args.force,
                )
            elif args.release_type == "curse":
                mpm.manager.release.curse(
                    pack_dir=args.pack_dir,
                    output_zip=args.output_zip,
                    packmodes=args.packmodes,
                    force=args.force,
                    mpm_filepath=MPM_FILE if args.include_mpm else None,
                )
            elif args.release_type == "serverfiles":
                mpm.manager.release.serverfiles(
                    pack_dir=args.pack_dir,
                    output_zip=args.output_zip,
                    packmodes=args.packmodes,
                    force=args.force,
                    mpm_filepath=MPM_FILE if args.include_mpm else None,
                )
        elif args.command == "update":
            if "pack_local" in args:
                if "update_zip" in args:
                    mpm.manager.update.update_zip(
                        pack_path=args.pack_local, zip_path=args.update_zip
                    )
                elif "update_http" in args:
                    mpm.manager.update.update_http(
                        pack_path=args.pack_local, http_url=args.update_http
                    )
            elif "install_ftp" in args:
                if "update_zip" in args:
                    mpm.manager.update.update_remote_zip(
                        ftp_url=args.install_ftp, zip_path=args.update_zip
                    )
                elif "update_http" in args:
                    mpm.manager.update.update_remote_http(
                        ftp_url=args.install_ftp, http_url=args.update_http
                    )

    except Exception as err:
        LOGGER.error(
            "Minecraft Pack Manager encountered an exception:\n\n%s",
            mpm.utils.err_str(err),
        )
        LOGGER.debug(
            "Detailed statcktrace:\n%s", "".join(traceback.format_tb(err.__traceback__))
        )
        print(
            "An exception occured, see above. The full stacktrace is available in the log file"
            "Exceptions are not yet handled in MPM, so this might be because of a wrong argument.\n"
            "If this is a problem in MPM, please fill in an issue at https://github.com/Riernar/mpm/issues"
            "and provide the log file"
        )
