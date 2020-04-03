# Standard library imports
from pathlib import Path

# local imports
from . import network as net
from . import utils


def build_new_modlist(pack_manifest, curse_manifest):
    """
    From an old pack_manifest and the curse_manifest file of the update
        compute the neew modlist in pack_manifest format
    
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


def complete_packmodes(pack_manifest):
    """
    Creates the GUI to assign unassigned mods and overrides to a packmode

    Arguments
        pack_manifest -- pack_manifest to complete packmode attributions on
    
    Returns
        pack_manifest. It is modified in-place according to the user input
    """
