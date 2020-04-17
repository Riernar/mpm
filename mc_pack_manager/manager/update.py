"""
Update management module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
import logging
from pathlib import Path
import requests
from typing import Union, List
import urllib.parse

# Local import
from .. import filesystem
from .. import manifest
from .. import network
from .. import utils
from ..manager import common

PathLike = Union[str, Path]
        
LOGGER = logging.getLogger("mpm.manager.update")

class UnhandledManifestURL(utils.AutoFormatError):
    """
    Exception for unhandled manifest url

    Attributes
        url -- the unhandled url
        message -- error explanation
    """
    def __init__(self, url, message="Cannot handle manifest url '{url}' for an update"):
        super().__init__(message)
        self.url = url
        self.message = message

def update_pack(
    install_url: str,
    manifest_url: str,
    packmodes: List[str]
):
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
        packmodes -- list of packmodes from the remote manifest to install
    """
    install_url = urllib.parse.urlparse(install_url)
    manifest_url = urllib.parse.urlparse(manifest_url)
    if manifest_url.scheme in ("http", "https"):
        update_pack_http(install_url, manifest_url, packmodes)
    elif manifest_url.scheme == "" and manifest_url.netloc == "" and manifest_url.path[:-3] == "zip":
        update_pack_zip(install_url, manifest, packmodes)
    else:
        raise UnhandledManifestURL(manifest_url)


def update_pack_http(
    install_url: urllib.parse.ParseResult,
    manifest_url: urllib.parse.ParseResult,
    packmodes: List[str]
):
    LOGGER.info("Updating from remote http manifest")
    with filesystem.get_filesystem(install_url) as lfs:
        # Get local configuration
        with lfs.open("pack-manifest.json") as f:
            local_manifest = manifest.pack.read(f)
        LOGGER.info("Local version is %s", local_manifest["pack-version"])
        LOGGER.info("Current packmodes are: %s", ", ".join(local_manifest.get("current-packmdoes", [])))
        # Get remote configuration
        LOGGER.info("Retrieving remote manifest")
        remote_manifest = manifest.pack.from_str(requests.get(manifest_url.geturl()).content)
        # Compute states
        local_packmodes = manifest.pack.get_all_dependencies(local_manifest["packmodes"], local_manifest["current-packmodes"])
        new_packmodes = manifest.pack.get_all_dependencies(remote_manifest["packmodes"], packmodes)
        # Quick comparison
        if remote_manifest["pack-version"] == local_manifest["pack_version"] and local_packmodes == new_packmodes:
            LOGGER.info("Nothing to update !")
            return
        else:
            LOGGER.info(
                "Updating to version %s, installing packmodes %s (including dependencies)",
                remote_manifest["pack-version"],
                ", ".join(packmode for packmode in sorted(new_packmodes))
            )
        # Update mods
        LOGGER.info("Updating mods")
        LOGGER.info("Computing mod difference")
        mod_diff = common.compute_mod_diff(
            manifest.pack.get_selected_mods(local_manifest, local_packmodes),
            manifest.pack.get_selected_mods(remote_manifest, new_packmodes),
            loglevel=logging.INFO
        )
        LOGGER.info("Applying mod difference")
        mod_dir = Path("mods")
        for addonID in mod_diff.deleted:
            mod = local_manifest["mods"][addonID]
            lfs.delete_file(mod_dir / mod["filename"])
        for addonID in mod_diff.updated:
            old_mod = local_manifest["mods"][addonID]
            lfs.delete_file(mod_dir / old_mod["filename"])
            new_mod = remote_manifest["mods"][addonID]
            lfs.download_in(
                network.TwitchAPI.get_download_url(addonID, new_mod["fileID"]),
                mod_dir / new_mod["filename"]
            )
        for addonID in mod_diff.added:
            mod = remote_manifest["mods"][addonID]
            lfs.download_in(
                network.TwitchAPI.get_download_url(addonID, mod["fileID"]),
                mod_dir / new_mod["filename"]
            )

        # Update overrides
        LOGGER.info("Updating overrides")
        LOGGER.info("Computing override difference")
        override_diff = common.compute_override_diff(
            manifest.pack.get_selected_overrides(local_manifest, local_packmodes),
            manifest.pack.get_selected_overrides(remote_manifest, new_packmodes),
            loglevel=logging.INFO
        )
        LOGGER.info("Applying override difference")
        remote_url = manifest_url._replace(path=str(Path(manifest_url.path).parent))
        remote_path = Path(remote_url.path)
        for override in override_diff.deleted:
            lfs.delete_file(override)
        for override in override_diff.updated:
            lfs.delete_file(override)
            lfs.download_in(
                remote_url._replace(
                    path=remote_path / "overrides" / override
                ).geturl(),
                override
            )
        for override in override_diff.added:
            lfs.download_in(
                remote_url._replace(
                    path=remote_path / "overrides" / override
                ).geturl(),
                override
            )
        # Write back new manifest
        raise NotImplementedError
    LOGGER.info("Done !")


def update_pack_zip(
    install_url: urllib.parse.ParseResult,
    manifest_url: PathLike,
    packmodes: List[str]
):
    raise NotImplementedError