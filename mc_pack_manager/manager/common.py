"""
Utility module for the manager package

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
from collections import namedtuple, OrderedDict
import logging
from pathlib import Path, PurePath
import shutil
from typing import List, Mapping, Union

# Local imports
from .. import network
from .. import utils

LOGGER = logging.getLogger("mpm.manager.common")

PathLike = Union[str, Path]

DiffObject = namedtuple("DiffObject", ["deleted", "updated", "added"])

####################
# MODS UTILS
####################


def format_modlist(
    modlist: List[Mapping[str, str]],
    print_version: bool = False,
    old_modlist: List[Mapping[str, str]] = None,
    old_modmap: Mapping[str, Mapping[str, str]] = None,
):
    """
    Formats a list of mods for logging

    Arguments
        modlist -- list of mods to format
        print_version -- adds the mod filename to the print
        old_modlist -- list of mods in a previous version. Ignored if old_modmap is provided
        old_modmap -- mapping from addonID to mods, for old version. Provides this if you already have it
    
    Returns
        A single string, the list of formatted mods ready for printing
    """
    SEP = "  - "
    if old_modlist and old_modmap is None:
        old_modmap = {mod["addonID"]: mod for mod in old_modlist}
    fmods = []
    sort_key = lambda mod: mod["name"]
    for mod in sorted(modlist, key=sort_key):
        fmod = mod["name"]
        if print_version:
            if old_modmap is None:
                fmod += " (%s)" % mod.get("filename", "UNRESOLVED")
            else:
                fmod += " (%s -> %s)" % (
                    old_modmap.get(mod["addonID"], {}).get("filename"),
                    mod.get("filename", "UNRESOLVED"),
                )
        fmods.append(fmod)
    return SEP + ("\n" + SEP).join(fmods)


def build_new_modlist(pack_manifest, curse_manifest):
    """
    From an old pack_manifest and the curse_manifest file of the update
        compute the new modlist in pack_manifest format
    
    Arguments
        pack_manifest -- the pack manifest of the current version
        curse_manifest -- the curse manifest of the next version
    
    Returns
        the "mods" property of the pack manifest for the new version. Mods
        not found in pack_manifest *won't* have a packmode "property"
    """
    LOGGER.info("Building new modlist")
    mod_map = {mod["addonID"]: mod for mod in pack_manifest["mods"]}
    LOGGER.info(
        "%s mods needs resolving, this might take a while",
        sum(
            1
            for fd in curse_manifest["files"]
            if (
                fd["projectID"] not in mod_map
                or "name" not in mod_map[fd["projectID"]]
                or mod_map[fd["projectID"]]["fileID"] != fd["fileID"]
                or (
                    mod_map[fd["projectID"]]["fileID"] == fd["fileID"]
                    and "filename" not in mod_map[fd["projectID"]]
                )
            )
        ),
    )
    new_mods = []
    for file_data in curse_manifest["files"]:
        addonID = file_data["projectID"]
        mod = {"addonID": addonID, "fileID": file_data["fileID"]}
        if addonID in mod_map and "packmode" in mod_map[addonID]:
            mod["packmode"] = mod_map[addonID]["packmode"]
        if addonID in mod_map and "name" in mod_map[addonID]:
            mod["name"] = mod_map[addonID]["name"]
        else:
            mod["name"] = network.TwitchAPI.get_addon_info(addonID)["name"]
            LOGGER.info("Resolved '%s'", mod["name"])
        if (
            addonID in mod_map
            and mod_map[addonID]["fileID"] == mod["fileID"]
            and "filename" in mod_map[addonID]
        ):
            mod["filename"] = mod_map[addonID]["filename"]
        else:
            mod["filename"] = network.TwitchAPI.get_file_info(addonID, mod["fileID"])[
                "fileName"
            ]
            LOGGER.info("Resolved '%s' to '%s'", mod["name"], mod["filename"])
        new_mods.append(mod)
    return new_mods


def compute_mod_diff(
    old_mods: List[Mapping[str, str]],
    new_mods: List[Mapping[str, str]],
    *,
    loglevel=None
) -> DiffObject:
    """
    Computes the difference between old and new modlists

    Arguments:
        old_mods -- the old mods ("mods" property of pack-manifest.json)
        new_mods -- the new mods ("mods" property of pack-manifest.json)
        loglevel -- if a logging level, logs the diff
    
    Returns
        a DiffObject on the addonID of the mods
    """
    LOGGER.info("Computing mod diff")
    old_addons = {mod["addonID"]: mod for mod in old_mods}
    new_addons = {mod["addonID"]: mod for mod in new_mods}
    updated = {
        addonID
        for addonID in new_addons.keys() & old_addons.keys()
        if old_addons[addonID]["fileID"] != new_addons[addonID]["fileID"]
    }
    diff = DiffObject(
        deleted=old_addons.keys() - new_addons.keys(),
        updated=updated,
        added=new_addons.keys() - old_addons.keys(),
    )
    LOGGER.info(
        "%s deleted, %s updated, %s added",
        len(diff.deleted),
        len(diff.updated),
        len(diff.added),
    )
    if loglevel is not None and loglevel < logging.INFO:
        LOGGER.info("Detailed lists logged to log file")
    if loglevel is not None and diff.deleted:
        LOGGER.log(
            loglevel,
            "The following mods were deleted:\n%s",
            format_modlist([old_addons[addonID] for addonID in diff.deleted]),
        )
    if loglevel is not None and diff.updated:
        LOGGER.log(
            loglevel,
            "The following mods were updated:\n%s",
            format_modlist(
                modlist=[new_addons[addonID] for addonID in diff.updated],
                old_modmap=old_addons,
                print_version=True,
            ),
        )
    if loglevel is not None and diff.added:
        LOGGER.log(
            loglevel,
            "The following mods were added:\n%s",
            format_modlist(
                [new_addons[addonID] for addonID in diff.added], print_version=True
            ),
        )
    return diff


####################
# OVERRIDES UTILS
####################


def build_overrides_cache(override_dir: Path) -> OrderedDict:
    """
    Builds the overrides cache of the pack_manifest for the new version

    Arguments
        overrides_dir -- path to the directory in which the curse zip
            file was extracted
    
    Returns
        The "overrides-cache" property of the pack_manifest for the update
    """
    LOGGER.info("Building override cache for %s", override_dir)
    override_dir = Path(override_dir)
    override_cache = {}
    for filepath in override_dir.rglob("*"):
        if filepath.is_file():
            rel_path = PurePath(filepath.relative_to(override_dir))
            if rel_path.as_posix() not in ("manifest.json", "pack-manifest.json"):
                override_cache[rel_path.as_posix()] = utils.file_hash(filepath)
    LOGGER.info("Sorting generated override cache")
    return OrderedDict(sorted(override_cache.items(), key=lambda t: t[0]))


def compute_override_diff(
    old_cache: OrderedDict, new_cache: OrderedDict, *, loglevel=None
) -> DiffObject:
    """
    Computes the difference between override caches

    Arguments
        old_cache -- 'override-cache' property of the old pack manifest
        new_cache -- 'override-cache' property of the new pack manifest
        loglevel -- log the diff at that logging level
    
    Returns
        A DiffObject on the overrides' filepath
    """
    LOGGER.info("Computing override diff")
    updated = {
        filepath
        for filepath in old_cache.keys() & new_cache.keys()
        if old_cache[filepath] != new_cache[filepath]
    }
    diff = DiffObject(
        deleted=old_cache.keys() - new_cache.keys(),
        updated=updated,
        added=new_cache.keys() - old_cache.keys(),
    )
    if loglevel is not None:
        for cat_name, filepath_set in zip(diff._fields, diff):
            if filepath_set:
                LOGGER.log(
                    loglevel,
                    "The following overrides were %s:\n  - %s",
                    cat_name,
                    "\n  - ".join(sorted(filepath_set)),
                )
    return diff


def apply_override_diff(target_dir: PathLike, source_dir: PathLike, diff: DiffObject):
    """
    Uses the diff between overrides to smartly update target_dir. Paths
    in diff are assumed to be relative to the provided directories

    Arguments
        target_dir -- directory to apply the diff in
        source_dir -- directory to find new file in
        diff -- the computed override diff
    """
    target_dir = Path(target_dir)
    source_dir = Path(source_dir)
    LOGGER.info("Applying override diff")
    LOGGER.info("Applying deletions")
    for path in sorted(diff.deleted):
        filepath = target_dir / path
        if filepath.is_file():
            LOGGER.debug("deleting %s", filepath)
            filepath.unlink()
        else:
            LOGGER.debug("Cannot delete %s, not an existing file", filepath)
    LOGGER.info("Applying updates")
    for path in sorted(diff.updated):
        trg_file = target_dir / path
        src_file = source_dir / path
        trg_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(src_file, trg_file)
            LOGGER.debug("Updated %s from %s", trg_file, src_file)
        except Exception as err:
            LOGGER.debug(
                "Couldn't update %s from %s:\n%s",
                trg_file,
                src_file,
                utils.err_str(err),
            )
    LOGGER.info("Applying additions")
    for path in sorted(diff.added):
        trg_file = target_dir / path
        src_file = source_dir / path
        trg_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(src_file, trg_file)
            LOGGER.debug("Added %s from %s", trg_file, src_file)
        except Exception as err:
            LOGGER.debug(
                "Couldn't add %s from %s:\n%s", trg_file, src_file, utils.err_str(err)
            )


####################
# PACK UTILS
####################


def check_snapshot_dir(pack_dir: PathLike):
    """
    Overly simple check that a directory is a snapshot dir
    """
    pack_dir = Path(pack_dir)
    if not pack_dir.exists():
        raise FileNotFoundError(pack_dir)
    if not pack_dir.is_dir():
        raise NotADirectoryError(pack_dir)
    if not (pack_dir / "pack-manifest.json").is_file():
        raise FileNotFoundError(
            "No pack-manifest.json file found in %s. Is this really a snapshot directory ?"
            % pack_dir
        )
    if not (pack_dir / "manifest.json").is_file():
        raise FileNotFoundError(
            "No manifest.json file found in %s. Is this really a snapshot directory ?"
            % pack_dir
        )
    if not (pack_dir / "overrides").is_dir():
        raise FileNotFoundError(
            "No overrides/ directory found in %s. Is this really a snapshot directory ?"
            % pack_dir
        )
