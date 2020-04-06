# Standard library imports
from pathlib import Path

# local imports
from . import network as net
from . import utils


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
    mod_map = {mod["addonID"]: mod for mod in pack_manifest["mods"]}
    new_mods = []
    for file_data in curse_manifest["files"]:
        addonID = file_data["addonID"]
        mod = {"addonID": addonID, "fileID": file_data["fileID"]}
        if "packmode" in mod_map[addonID]:
            mod["packmode"] = mod_map[addonID]["packmode"]
        if "name" in mod_map[addonID]:
            mod["name"] = mod_map[addonID]["name"]
        else:
            mod["name"] = net.TwitchAPI.get_addon_info(addonID)["name"]
        new_mods.append(mod)
    return new_mods


def build_overrides_cache(overrides_dir: Path):
    """
    Builds the overrides cache of the pack_manifest for the new version

    Arguments
        overrides_dir -- path to the directory in which the curse zip
            file was extracted
    
    Returns
        The "overrides-cache" property of the pack_manifest for the update
    """
    overrides_dir = Path(overrides_dir)
    overrides_cache = []
    for filepath in overrides_dir.rglob("*"):
        if filepath.is_file():
            rel_path = filepath.relative_to(overrides_dir)
            if str(rel_path) not in ("manifest.json", "pack-manifest.json"):
                overrides_cache.append(
                    {"filepath": str(rel_path), "hash": utils.file_hash(filepath)}
                )
    return sorted(overrides_cache, key=lambda cached: cached["filepath"])


def snapshot():
    """
    Creates a pack manager representation from a curse/twitch modpack

    Arguments:
        curse_zip -- .zip file exported by curse
        pack_dir -- local dir into which to build or update the modpack representation
    """
    raise NotImplementedError


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
