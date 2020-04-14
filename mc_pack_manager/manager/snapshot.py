"""
Snapshot management module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Union
import zipfile

# Local imports
from .. import manifest
from .. import ui
from ..manager import common

LOGGER = logging.getLogger("mpm.manager.snapshot")

PathLike = Union[str, Path]


def snapshot(pack_dir: PathLike, curse_zip: PathLike, version_incr=0):
    """
    Creates a pack manager representation from a curse/twitch modpack

    Arguments:
        pack_dir -- local dir in which to build or update the new modpack representation
        curse_zip -- path to the zip file exported by curse/twitch app
        version_incr -- which version to increase: (0 patch, 1 minor, 2 major)
    """
    pack_dir = Path(pack_dir)
    curse_zip = Path(curse_zip)
    if pack_dir.is_file():
        raise NotADirectoryError(pack_dir)
    if not curse_zip.exists():
        raise FileNotFoundError(curse_zip)
    if curse_zip.is_dir():
        raise IsADirectoryError(curse_zip)
    if not zipfile.is_zipfile(curse_zip):
        raise zipfile.BadZipFile("%s is not a zip file" % curse_zip)
    # Prepare pack_dir
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack_manifest = manifest.pack.load_from(pack_dir)

    with tempfile.TemporaryDirectory(dir=".") as temp_dir:
        temp_dir = Path(temp_dir)
        # unpack curse dir
        LOGGER.info("Decompressing %s", curse_zip)
        with zipfile.ZipFile(curse_zip) as zf:
            zf.extractall(temp_dir)
        # read curse manifest
        LOGGER.info("Reading curse zip content")
        ## Manifest
        curse_manifest = manifest.curse.read(temp_dir / "manifest.json")
        ## Build new modlist
        new_modlist = common.build_new_modlist(pack_manifest, curse_manifest)
        ## Build new overrides
        new_override_cache = common.build_overrides_cache(
            temp_dir / curse_manifest["overrides"]
        )

        # diffs
        LOGGER.info("Computing diff")
        ## Mods
        common.compute_mod_diff(
            old_mods=pack_manifest["mods"], new_mods=new_modlist, loglevel=logging.DEBUG
        )
        ## Overrides
        override_diff = common.compute_override_diff(
            old_cache=pack_manifest["override-cache"],
            new_cache=new_override_cache,
            logelevel=logging.DEBUG,
        )

        # Packmodes assignements
        LOGGER.info("Starting packmode assignements Usr Interface")
        packmodes = pack_manifest["packmodes"]
        ## Mods
        packmodes, new_modlist = ui.assign_mods(packmodes, new_modlist)
        ## Overrides
        packmodes, overrides = ui.assign_overrides(
            packmodes,
            pack_manifest["overrides"],
            new_override_cache,
            override_diff.added,
        )

        # Create new manifest
        new_pack_manifest = manifest.pack.make(
            pack_version=pack_manifest["pack-version"].incr(
                min(max(int(version_incr), 0), 2)
            ),
            packmodes=packmodes,
            mods=new_modlist,
            overrides=overrides,
            override_cache=new_override_cache,
            current_packmodes=pack_manifest.get("current-packmodes"),
            overrides_url=pack_manifest.get("overrides-url"),
        )

        # New repr creation
        ## Cleanup content of pack_dir
        LOGGER.info("Cleaning up odl representation")
        for filepath in pack_dir.iterdir():
            if filepath.is_file() and filepath.name != "pack-manifest.json":
                LOGGER.debug("Deleted %s", filepath)
                filepath.unlink()
            elif filepath.is_dir() and filepath.stem != "overrides":
                LOGGER.debug("Deleted %s", filepath)
                filepath.rmdir()
        ## Copy content of curse .zip
        LOGGER.info("Copying curse .zip extra content")
        for filepath in temp_dir.iterdir():
            if filepath.is_file():
                dst = pack_dir / filepath.relative_to(temp_dir)
                shutil.copyfile(src=filepath, dst=dst)
                LOGGER.debug("Copied %s to %s", filepath, dst)
            elif filepath.is_dir() and filepath.stem != curse_manifest["overrides"]:
                dst = pack_dir / filepath.relative_to(temp_dir)
                shutil.copytree(src=filepath, dst=dst, copy_function=shutil.copyfile)
                LOGGER.debug("Recursively copied %s into %s", filepath, dst)
        ## Apply override diff
        common.apply_override_diff(
            target_dir=pack_dir / "overrides",
            source_dir=temp_dir / curse_manifest["overrides"],
            diff=override_diff,
        )
        ## manifest
        manifest.pack.write(new_pack_manifest, pack_dir / "pack-manifest.json")

    LOGGER.info("Deleting temporary dir %s", temp_dir)
    LOGGER.info("Done !")
