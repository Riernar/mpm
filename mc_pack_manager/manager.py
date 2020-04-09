"""
Part of the Minecraft Pack Manager utility (mpm)

Main interface
"""
# Standard library imports
from collections import namedtuple, OrderedDict
import logging
from pathlib import Path, PurePath
import shutil
import tempfile
from typing import Union, List, Mapping
import zipfile

# local imports
from . import gui
from . import manifest
from . import network
from . import utils

LOGGER = logging.getLogger("mpm.manager")
DiffObject = namedtuple("DiffObject", ["deleted", "updated", "added"])
PathLike = Union[str, Path]


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
        new_mods.append(mod)
    return new_mods


def compute_mod_diff(
    old_mods: List[Mapping[str, str]],
    new_mods: List[Mapping[str, str]],
    *,
    loglevel=None
):
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
    sort_key = lambda addonID: old_addons.get(addonID, new_addons.get(addonID))["name"]
    if loglevel is not None and diff.deleted:
        modlist = "\n  - ".join(
            sort_key(addonID) for addonID in sorted(diff.deleted, key=sort_key)
        )
        LOGGER.log(loglevel, "The following mods were deleted:\n  - %s", modlist)
    if loglevel is not None and diff.updated:
        modlist = []
        for addonID in sorted(diff.updated, key=sort_key):
            name = old_addons[addonID]["name"]
            old_version = (
                old_addons[addonID]["filename"]
                if "filename" in old_addons[addonID]
                else network.TwitchAPI.get_file_info(
                    addonID, old_addons[addonID]["fileID"]
                )["fileName"]
            )
            new_version = (
                new_addons[addonID]["filename"]
                if "filename" in new_addons[addonID]
                else network.TwitchAPI.get_file_info(
                    addonID, new_addons[addonID]["fileID"]
                )["fileName"]
            )
            modlist.append("%s (%s -> %s)" % (name, old_version, new_version))
        LOGGER.log(
            loglevel, "The following mods were updated:\n  - %s", "\n  - ".join(modlist)
        )
    if loglevel is not None and diff.added:
        modlist = []
        for addonID in sorted(diff.added, key=sort_key):
            name = new_addons[addonID]["name"]
            version = (
                new_addons[addonID]["filename"]
                if "filename" in new_addons[addonID]
                else network.TwitchAPI.get_file_info(
                    addonID, new_addons[addonID]["fileID"]
                )["fileName"]
            )
            modlist.append("%s (%s)" % (name, version))
        LOGGER.log(
            loglevel, "The following mods were added:\n  - %s", "\n  - ".join(modlist)
        )
    return diff


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
            if str(rel_path) not in ("manifest.json", "pack-manifest.json"):
                override_cache[str(rel_path)] = utils.file_hash(filepath)
    LOGGER.info("Sorting generated override cache")
    return OrderedDict(sorted(override_cache.items(), key=lambda t: t[0]))


def compute_override_diff(
    old_cache: OrderedDict, new_cache: OrderedDict, *, logelevel=None
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
    if logelevel is not None:
        for cat_name, filepath_set in zip(diff._fields, diff):
            if filepath_set:
                LOGGER.log(
                    logelevel,
                    "The following overrides were %s:\n  - %s",
                    cat_name,
                    "\n  - ".join(sorted(filepath_set)),
                )
    return diff


def apply_override_diff(target_dir, source_dir, diff):
    """
    Uses the diff between overrides to smartly update target_dir. Pathes
    in diff are assuled to be relative to the provided directories

    Arguments
        target_dir -- directory to apply the diff in
        source_dir -- directory to find new file in
        diff -- the computed override diff
    """
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
        trg_file.mkdir(parents=True, exists_ok=True)
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


def snapshot(pack_dir: PathLike, curse_zip: PathLike):
    """
    Creates a pack manager representation from a curse/twitch modpack

    Arguments:
        pack_dir -- local dir in which to build or update the new modpack representation
        curse_zip -- path to the zip file exported by curse/twitch app
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
    pack_manifest = manifest.get_pack_manifest(pack_dir)

    with tempfile.TemporaryDirectory(dir=".") as temp_dir:
        temp_dir = Path(temp_dir)
        # unpack curse dir
        LOGGER.info("Decompressing %s", curse_zip)
        with zipfile.ZipFile(curse_zip) as zf:
            zf.extractall(temp_dir)
        # read curse manifest
        LOGGER.info("Reading curse zip content")
        ## Manifest
        curse_manifest = manifest.read_curse_manifest(temp_dir / "manifest.json")
        ## Build new modlist
        new_modlist = build_new_modlist(pack_manifest, curse_manifest)
        ## Build new overrides
        new_override_cache = build_overrides_cache(
            temp_dir / curse_manifest["overrides"]
        )

        # diffs
        LOGGER.info("Computing diff")
        ## Mods
        compute_mod_diff(
            old_mods=pack_manifest["mods"], new_mods=new_modlist, loglevel=logging.INFO
        )
        ## Overrides
        override_diff = compute_override_diff(
            old_cache=pack_manifest["override-cache"],
            new_cache=new_override_cache,
            logelevel=logging.INFO,
        )

        # Packmodes assignements
        LOGGER.info("Starting packmode assignements GUI")
        packmodes = pack_manifest["packmodes"]
        ## Mods
        packmodes, new_modlist = gui.assign_mods(packmodes, new_modlist)
        ## Overrides
        packmodes, overrides = gui.assign_overrides(
            packmodes, pack_manifest["overrides"], new_override_cache
        )

        # Create new manifest
        new_pack_manifest = manifest.make_pack_manifest(
            pack_version=pack_manifest["pack-version"].incr(),
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
        apply_override_diff(
            target_dir=pack_dir / "overrides",
            source_dir=temp_dir / curse_manifest["overrides"],
            diff=override_diff,
        )
        ## manifest
        manifest.write_pack_manifest(new_pack_manifest, pack_dir / "pack-manifest.json")

    LOGGER.info("Deleting temporary dir %s", temp_dir)


def release_mpm():
    """
    Creates a .zip useable by the update functionnality of the pack manager

    Arguments
        pack_dir -- local dir containing the pack manager's modpack representation (see snapshot())
        output_file -- path to the output file to produce
    """
    raise NotImplementedError


def release_curse():
    """
    Creates a .zip of the same format as curse/twitch that can be used to do a fresh install
        of the pack. This will *not* contain mods, but creates a manifest that list them (same
        thing curse does)

    Arguments
        pack_dir -- local dir containing the pack manager's modpack representation (see snapshot())
        output_file -- path to the output file to produce
        packmodes -- list of packmodes to include into the created .zip. Can be "ALL" to include them all
        include_mpm -- bundle this pack manager into the .zip, so that it is part of the pack
    """
    raise NotImplementedError


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


def update_pack():
    """
    Updates a modpack installation

    Arguments
        install_dir -- modpack installation to update. Can be
            - a local path to the "minecraft/" directory of a modpack install
            - an FTP url to a remote "minecraft/" directory
        pack_manifest -- link to pack-manifest.json file to use for the update. Can be
            - a local path to the .zip created by 'release_mpm()'
            - an url to the pack-manifest.json created inside the above zip. The url will be
                reused to find overrides (i.e. you have a web server exposing the content of the zip)
    """
    raise NotImplementedError
