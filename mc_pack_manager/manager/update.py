"""
Update management module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
from abc import ABC, abstractmethod
import logging
from pathlib import Path
import requests
import tempfile
from typing import Union, List
import urllib.parse
import zipfile

# Local import
from .. import filesystem
from .. import manifest
from .. import network
from .. import utils
from ..manager import common

PathLike = Union[str, Path]

LOGGER = logging.getLogger("mpm.manager.update")

class UpdateProvider(ABC):
    """
    Provides the files for the update
    """
    @abstractmethod
    def __enter__(self):
        """
        Context manager interface
        """
    
    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager interface
        """

    @abstractmethod
    def get_manifest(self) -> dict:
        """
        Returns the update pack manifest as a string
        """
    
    @abstractmethod
    def install_mod(self, fs: filesystem.common.FileSystem, addonID:str):
        """
        Installs a mod on the provided filesystem
        """
    
    @abstractmethod
    def install_override(self, fs: filesystem.common.FileSystem, override: str):
        """
        Installs an override on the provided filesystem
        """

class LocalUpdateProvider(UpdateProvider):
    """
    Updates from a local zip file
    """
    def __init__(self, zip_path: PathLike):
        self.zip_path = Path(zip_path)
        if not zipfile.is_zipfile(self.zip_path):
            raise ValueError("%s is not a zip file" % self.zip_path)
        self.temp_dir = None
        self.root = None
        self.manifest = None
    
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=".")
        self.root = Path(self.temp_dir)
        with zipfile.ZipFile(self.zip_path) as zf:
            zf.extractall(self.temp_dir)
        manifest_path = self.root / "pack-manifest.json"
        if not manifest_path.is_file():
            raise ValueError("The update zip does not contain a manifets")
        self.manifest = manifest.pack.read(manifest_path)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.temp_dir.cleanup()
    
    def get_manifest(self):
        if self.manifest is None:
            raise RuntimeError("UpdateProvider object must be used in a with statement")
        return self.manifest
    
    def install_mod(self, fs: filesystem.common.FileSystem, addonID: str):
        if self.manifest is None:
            raise RuntimeError("UpdateProvider object must be used in a with statement")
        mod = self.manifest["mods"][addonID]
        fs.download(
            network.TwitchAPI.get_download_url(addonID, mod["fileID"]),
            "mods/" +  mod["filename"],
        )
    
    def install_override(self, fs: filesystem.common.FileSystem, override: str):
        if self.manifest is None:
            raise RuntimeError("UpdateProvider object must be used in a with statement")
        fs.send_file(
            self.root / "overrides" / override,
            "overrides/" + override
        )


class HTTPUpdateProvider(UpdateProvider):
    """
    Update from an HTTP(S) link
    """
    def __init__(self, url):
        self.url = urllib.parse.urlparse(url)
        if self.url.scheme not in ("http", "https"):
            raise ValueError("URL must be HTTP(s)")
        self.path = Path(self.url.path)
        try:
            self.manifest = manifest.pack.from_str(
                requests.get(self.url._replace(path=str(self.path/"pack-manifest.json")).geturl()).content
            )
        except Exception as err:
            LOGGER.debug("Exception: %s", utils.err_str(err))
            raise ValueError("URL is invalid, it doesn't have a pack-manifest.json")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_manifest(self):
        return self.manifest
    
    def install_mod(self, fs: filesystem.common.FileSystem, addonID: str):
        mod = self.manifest["mods"][addonID]
        fs.download(
            network.TwitchAPI.get_download_url(addonID, mod["fileID"]),
            "mods/" +  mod["filename"],
        )

    def install_override(self, fs: filesystem.common.FileSystem, override: str):
        fs.download(
            self.url._replace(path=str(self.path / "overrides" / override)).geturl(),
            override
        )


def update_http(
    pack_path: PathLike,
    http_url: str,
    packmodes: List[str]=None
):
    """
    Update a local pack directory from an http server

    Arguments
        pack_path -- path to the pack directory to update
        http_url -- url to the root of the server exposing the update
        packmodes -- optional list of packmodes to install
    """
    pack = Path(pack_path)
    if not pack.is_dir():
        raise NotADirectoryError(pack)
    with HTTPUpdateProvider(http_url) as update, filesystem.local.LocalFileSystem(pack) as fs:
        update_pack(update, fs, packmodes)

def update_zip(
    pack_path: PathLike,
    zip_path: PathLike,
    packmodes: List[str]=None
):
    """
    Updates a local pack directory from a local zip mpm release

    Arguments
        pack_path -- path to the pack directory to update
        zip_path -- path to the local zip mpm release
        packmodes -- optional list of packmodes to install
    """
    pack = Path(pack_path)
    if not pack.is_dir():
        raise NotADirectoryError(pack)
    with LocalUpdateProvider(zip_path) as update, filesystem.LocalFileSystem(pack) as fs:
        update_pack(update, fs, packmodes)

def update_remote_http(
    ftp_url: str,
    http_url: str,
    packmodes: List[str] = ("server")
):
    """
    Updates a remote pack (over ftp) from an http server

    Arguments
        ftp_url -- url to the remote ftp filesystem
        http_url -- url to the root of the server exposing the update
        packmodes -- optional list of packmodes to install
    """
    with HTTPUpdateProvider(http_url) as update, filesystem.FTPFileSystem.from_url(ftp_url) as fs:
        update_pack(update, fs, packmodes)

def update_remote_zip(
    ftp_url: str,
    zip_path: PathLike,
    packmodes: List[str] = ("server")
):
    """
    Updates a remote pack (over ftp) from a local zip mpm release

    Arguments
        ftp_url -- url to the remote ftp filesystem
        zip_path -- path to the local zip mpm release
        packmodes -- optional list of packmodes to install
    """
    with LocalUpdateProvider(zip_path) as update, filesystem.FTPFileSystem.from_url(ftp_url) as fs:
        update_pack(update, fs, packmodes)

def update_pack(
    update: UpdateProvider,
    fs: filesystem.common.FileSystem,
    packmodes: List[str]=None,
):
    """
    Performs a pack update

    Arguments
        update -- UpdateProvied object that will provide update files
        fs -- a filesystem object to the pack to update
    """
    LOGGER.info("Starting update")
    # Get local configuration
    with fs.open("pack-manifest.json") as f:
        local_manifest = manifest.pack.read(f)
    LOGGER.info("Local version is %s", local_manifest["pack-version"])
    LOGGER.info(
        "Current packmodes are: %s",
        ", ".join(local_manifest.get("current-packmdoes", [])),
    )
    # Get remote configuration
    LOGGER.info("Retrieving remote manifest")
    remote_manifest = update.get_manifest()
    # Compute states
    local_packmodes = manifest.pack.get_all_dependencies(
        local_manifest["packmodes"], local_manifest["current-packmodes"]
    )
    new_packmodes = manifest.pack.get_all_dependencies(
        remote_manifest["packmodes"], packmodes
    )
    # Quick comparison
    if (
        remote_manifest["pack-version"] == local_manifest["pack_version"]
        and local_packmodes == new_packmodes
    ):
        LOGGER.info("Nothing to update !")
        return
    else:
        LOGGER.info(
            "Updating to version %s, installing packmodes %s (including dependencies)",
            remote_manifest["pack-version"],
            ", ".join(packmode for packmode in sorted(new_packmodes)),
        )
    # Update mods
    LOGGER.info("Updating mods")
    LOGGER.info("Computing mod difference")
    mod_diff = common.compute_mod_diff(
        manifest.pack.get_selected_mods(local_manifest, local_packmodes),
        manifest.pack.get_selected_mods(remote_manifest, new_packmodes),
        loglevel=logging.INFO,
    )
    LOGGER.info("Applying mod difference")
    mod_dir = Path("mods")
    for addonID in mod_diff.deleted:
        mod = local_manifest["mods"][addonID]
        fs.unlink(mod_dir / mod["filename"])
    for addonID in mod_diff.updated:
        old_mod = local_manifest["mods"][addonID]
        fs.unlink(mod_dir / old_mod["filename"])
        update.install_mod(filesystem, addonID)
    for addonID in mod_diff.added:
        update.install_mod(fs, addonID)

    # Update overrides
    LOGGER.info("Updating overrides")
    LOGGER.info("Computing override difference")
    override_diff = common.compute_override_diff(
        manifest.pack.get_selected_overrides(local_manifest, local_packmodes),
        manifest.pack.get_selected_overrides(remote_manifest, new_packmodes),
        loglevel=logging.INFO,
    )
    LOGGER.info("Applying override difference")
    #remote_url = manifest_url._replace(path=str(Path(manifest_url.path).parent))
    #remote_path = Path(remote_url.path)
    for override in override_diff.deleted:
        fs.unlink(override)
    for override in override_diff.updated:
        fs.unlink(override)
        update.install_override(fs, override)
    for override in override_diff.added:
        update.install_override(fs, override)
    # Write new manifest to save current state
    new_manifest = manifest.pack.make(
        pack_version=remote_manifest["pack-version"],
        packmodes=remote_manifest["packmodes"],
        mods=remote_manifest["mods"],
        overrides=remote_manifest["overrides"],
        override_cache=remote_manifest["override-cache"],
        current_packmodes=packmodes,
    )
    with fs.open("pack-manifest.json", "wt") as f:
        manifest.pack.dump(new_manifest, f)
    LOGGER.info("Done !")