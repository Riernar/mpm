"""
Snapshot management module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
import contextlib
import enum
import logging
from pathlib import Path, PurePath
import shutil
import tempfile
from typing import Union
import zipfile

# Local imports
from .. import _filelist
from .. import manifest
from .. import ui
from ..manager import common

LOGGER = logging.getLogger("mpm.manager.snapshot")

PathLike = Union[str, Path]


class VersionIncr(enum.Enum):
    MINOR = (("minor",), 0)
    MEDIUM = (("medium",), 1)
    MAJOR = (("major",), 2)

    def __new__(cls, aliases, value=0):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.aliases = aliases
        return obj

    @classmethod
    def _missing_(cls, value):
        string = str(value).lower()
        for member in cls:
            if string in member.aliases:
                return member


def snapshot(
    curse_zip: PathLike,
    snapshot: PathLike,
    version_incr: VersionIncr = 0,
    mpm_filepath=None,
):
    """
    Creates a pack manager representation from a curse/twitch modpack

    Arguments:
        snapshot -- path to the snapshot to create or update
        curse_zip -- path to the zip file exported by curse/twitch app
        version_incr -- which version to increase: (0 patch, 1 minor, 2 major)
    """
    snapshot = Path(snapshot)
    curse_zip = Path(curse_zip)
    version_incr = VersionIncr(version_incr)
    if not curse_zip.exists():
        raise FileNotFoundError(curse_zip)
    if curse_zip.is_dir():
        raise IsADirectoryError(curse_zip)
    if not zipfile.is_zipfile(curse_zip):
        raise zipfile.BadZipFile("%s is not a zip file" % curse_zip)
    if snapshot.exists() and not zipfile.is_zipfile(snapshot):
        raise zipfile.BadZipFile("%s is not a zip file" % snapshot)
    # Create work directories
    with tempfile.TemporaryDirectory(dir=".") as temp_snap, tempfile.TemporaryDirectory(
        dir="."
    ) as temp_curse:
        temp_snap = Path(temp_snap)
        temp_curse = Path(temp_curse)
        # Extract previous snapshot, if any
        if snapshot.exists():
            LOGGER.info("Decompressing previous snapshot %s", snapshot)
            with zipfile.ZipFile(snapshot) as zf:
                zf.extractall(temp_snap)
        # Retrieve previous manifest or default
        pack_manifest = manifest.pack.read_from(temp_snap)
        # unpack curse dir
        LOGGER.info("Decompressing curse modpack %s", curse_zip)
        with zipfile.ZipFile(curse_zip) as zf:
            zf.extractall(temp_curse)
        # read curse manifest
        LOGGER.info("Reading curse zip content")
        ## Manifest
        curse_manifest = manifest.curse.read(temp_curse / "manifest.json")
        ## Build new modlist
        new_modlist = common.build_new_modlist(pack_manifest, curse_manifest)
        ## Build new overrides
        ### Include MPM is needed
        if mpm_filepath is not None:
            LOGGER.info("Adding mpm to the overrides before scanning")
            mpm_filepath = Path(mpm_filepath)
            base_path = temp_curse / curse_manifest["overrides"] / "mpm"
            base_path.mkdir(exist_ok=True, parents=True)
            LOGGER.debug("Adding %s", mpm_filepath.name)
            dst = base_path / mpm_filepath.name
            if dst.is_file():
                dst.unlink()
            shutil.copyfile(src=mpm_filepath, dst=dst)
            LOGGER.debug("Adding %s", "requirements.txt")
            dst = base_path / "requirements.txt"
            if dst.is_file():
                dst.unlink()
            shutil.copyfile(src=mpm_filepath.parent / "requirements.txt", dst=dst)
            for source_file in _filelist.MPM_SRC_FILES:
                LOGGER.debug("Adding %s", source_file.relative_to(mpm_filepath.parent))
                dst = base_path / source_file.relative_to(mpm_filepath.parent)
                dst.parent.mkdir(exist_ok=True, parents=True)
                if dst.is_file():
                    dst.unlink()
                shutil.copyfile(src=source_file, dst=dst)
        new_override_cache = common.build_overrides_cache(
            temp_curse / curse_manifest["overrides"]
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
            loglevel=logging.DEBUG,
        )
        # Packmodes assignements
        LOGGER.info("Starting packmode assignements User Interface")
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
            pack_version=pack_manifest["pack-version"].incr(version_incr._value_),
            packmodes=packmodes,
            mods=new_modlist,
            overrides=overrides,
            override_cache=new_override_cache,
            current_packmodes=pack_manifest.get("current-packmodes"),
        )

        # New repr creation
        ## Cleanup content of pack_dir
        LOGGER.info("Cleaning up old representation")
        for filepath in temp_snap.iterdir():
            if filepath.is_file() and filepath.name != "pack-manifest.json":
                LOGGER.debug("Deleted %s", filepath)
                filepath.unlink()
            elif filepath.is_dir() and filepath.stem != "overrides":
                LOGGER.debug("Deleted %s", filepath)
                filepath.rmdir()
        ## Copy content of curse .zip
        LOGGER.info("Copying curse .zip extra content")
        for filepath in temp_curse.iterdir():
            if filepath.is_file():
                dst = temp_snap / filepath.relative_to(temp_curse)
                shutil.copyfile(src=filepath, dst=dst)
                LOGGER.debug("Copied %s to %s", filepath, dst)
            elif filepath.is_dir() and filepath.stem != curse_manifest["overrides"]:
                dst = temp_snap / filepath.relative_to(temp_curse)
                shutil.copytree(src=filepath, dst=dst, copy_function=shutil.copyfile)
                LOGGER.debug("Recursively copied %s into %s", filepath, dst)
        ## Apply override diff
        common.apply_override_diff(
            target_dir=temp_snap / "overrides",
            source_dir=temp_curse / curse_manifest["overrides"],
            diff=override_diff,
        )
        ## manifest
        manifest.pack.write(new_pack_manifest, temp_snap / "pack-manifest.json")

        # Prepare snapshot directory
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info("Compressing new snapshot")
        with zipfile.ZipFile(
            snapshot, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6,
        ) as archive:
            for element in temp_snap.rglob("*"):
                if element.is_file():
                    archive.write(
                        filename=element, arcname=element.relative_to(temp_snap)
                    )
        LOGGER.info("Compressed")
        LOGGER.info("Deleting temporary directories %s and %s", temp_snap, temp_curse)
    LOGGER.info("Done !")
