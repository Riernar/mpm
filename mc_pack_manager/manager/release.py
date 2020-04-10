"""
Release management module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
import json
import logging
from pathlib import Path
from typing import Union
import zipfile

# Local import
from .. import manifest
from ..manager import common

LOGGER = logging.getLogger("mpm.manager.release")

PathLike = Union[str, Path]

def mpm(pack_dir: PathLike, output_file: PathLike, force=False):
    """
    Creates a .zip useable by the update functionnality of the pack manager

    Arguments
        pack_dir -- local dir containing the pack manager's modpack representation (see snapshot())
        output_file -- path to the output file to produce
        force -- erase output_file if it already exists
    """
    pack_dir = Path(pack_dir)
    output_file = Path(output_file)
    common.check_snapshot_dir(pack_dir)
    LOGGER.info("Creating mpm release in %s", output_file)
    with zipfile.ZipFile(
        output_file,
        mode="w" if force else "x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for element in pack_dir.rglob("*"):
            if element.is_file():
                archive.write(filename=element, arcname=element.relative_to(pack_dir))
    LOGGER.info("Done !")


def curse(
    pack_dir: PathLike,
    output_zip: PathLike,
    packmodes=None,
    force=False,
    include_mpm=False,
):
    """
    Creates a .zip of the same format as curse/twitch that can be used to do a fresh install
        of the pack. This will *not* contain mods, but creates a manifest that list them (same
        thing curse does)

    Arguments
        pack_dir -- local dir containing the pack manager's modpack representation (see snapshot())
        output_file -- path to the output file to produce
        packmodes -- list of packmodes to include into the created .zip. Defaults to everything
        force -- erase output_zip if it already exists
        include_mpm -- bundle this pack manager into the .zip, so that it is part of the pack
    """
    # File checks and opening
    pack_dir = Path(pack_dir)
    output_zip = Path(output_zip)
    common.check_snapshot_dir(pack_dir)
    # Read manifest
    pack_manifest = manifest.pack.load_from(pack_dir)
    curse_manifest = manifest.curse.read(pack_dir / "manifest.json")
    # Check packmodes
    if packmodes:
        manifest.pack.check_packmodes(pack_manifest["packmodes"], packmodes)
    # Open zip archive
    LOGGER.info("Opening .zip file")
    archive = zipfile.ZipFile(
        output_zip,
        mode="w" if force else "x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    )
    # Compute mods
    if not packmodes:
        LOGGER.info("No 'packmodes' argument, using all packmodes")
        selected_mods = pack_manifest["mods"]
    else:
        selected_mods = manifest.pack.get_selected_mods(pack_manifest, packmodes)
    LOGGER.debug(
        "Selected mods:\n%s", common.format_modlist(selected_mods, print_version=True)
    )
    # Create new manifest
    LOGGER.info("Generating new manifest")
    curse_manifest["files"] = [
        {"projectID": mod["addonID"], "fileID": mod["fileID"], "required": True}
        for mod in selected_mods
    ]
    curse_manifest["version"] = str(pack_manifest["pack-version"])
    curse_manifest["overrides"] = "overrides"
    with archive.open("manifest.json", mode="w") as f:
        f.write(json.dumps(curse_manifest, indent=4).encode("utf-8"))
    # Compute overrides
    if not packmodes:
        LOGGER.info("No 'packmodes' argument, using all overrides")
        selected_overrides = pack_manifest["override-cache"]
    else:
        selected_overrides = manifest.pack.get_selected_overrides(pack_manifest, packmodes)
    LOGGER.debug(
        "Selected overrides:\n  - %s",
        "\n  - ".join(selected_overrides.keys()),
    )
    # Compress overrides
    LOGGER.info("Adding selected overrides to .zip archive")
    for filepath in selected_overrides.keys():
        path = pack_dir / "overrides" / filepath
        archive.write(filename=path, arcname=path.relative_to(pack_dir))
    # Includes extra files (e.g. modlist)
    LOGGER.info("Adding extra modpack files to .zip archives")
    for extra in pack_dir.glob("*"):
        if extra.is_file() and extra.name not in (
            "manifest.json",
            "pack-manifest.json",
        ):
            archive.write(filename=extra, arcname=extra.relative_to(pack_dir))
        elif extra.is_dir() and extra.stem != "overrides":
            for sub_extra in extra.rglob("*"):
                archive.write(
                    filename=sub_extra, arcname=sub_extra.relative_to(pack_dir)
                )
    ## Include MPM
    if include_mpm:
        LOGGER.info("Adding mpm to .zip archive")
        LOGGER.fatal("ADDING MPM IS NOT YET SUPPORTED !")
    archive.close()
    LOGGER.info("Done !")


def release_zip():
    """
    Creates a .zip that readily contains mods and everything else for the pack. Useful to make
        server files for instance.
    WARNING: be mindful of mods licenses before redistributing this zip !
    
    Arguments
        pack_dir -- local dir containing the pack manager's modpack representation (see snapshot())
        output_file -- path to the output file to produce
        packmodes -- list of packmodes to include into the created .zip. Can be "ALL" to include them all
        include_mpm -- bundle this pack manager into the .zip, so that it is part of the pack
    """
    raise NotImplementedError