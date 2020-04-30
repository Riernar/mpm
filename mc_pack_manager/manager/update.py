"""
Update management module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
from abc import ABC, abstractmethod
import enum
import logging
from pathlib import Path
import requests
import sys
import tempfile
from typing import Union, List
import urllib.parse
import zipfile

# Local import
from .. import filesystem
from .. import manifest
from .. import network
from .. import ui
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
    def install_mod(self, fs: filesystem.common.FileSystem, addonID: str):
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
        self.root = Path(self.temp_dir.__enter__())
        with zipfile.ZipFile(self.zip_path) as zf:
            zf.extractall(self.root)
        manifest_path = self.root / "pack-manifest.json"
        if not manifest_path.is_file():
            raise ValueError("The update zip does not contain a manifets")
        self.manifest = manifest.pack.read(manifest_path)
        self.mod_map = {mod["addonID"]: mod for mod in self.manifest["mods"]}
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.temp_dir.__exit__(exc_type, exc_value, traceback)

    def get_manifest(self):
        if self.manifest is None:
            raise RuntimeError("UpdateProvider object must be used in a with statement")
        return self.manifest

    def install_mod(self, fs: filesystem.common.FileSystem, addonID: str):
        if self.manifest is None:
            raise RuntimeError("UpdateProvider object must be used in a with statement")
        mod = self.mod_map.get(addonID, None)
        if mod is None:
            LOGGER.error("Tryied to install invalid mod with id %s, skipping", addonID)
            return
        LOGGER.info("Downloading mod %s", mod.get("name", addonID))
        fs.download(
            network.TwitchAPI.get_download_url(addonID, mod["fileID"]),
            "mods/" + mod["filename"],
        )

    def install_override(self, fs: filesystem.common.FileSystem, override: str):
        if self.manifest is None:
            raise RuntimeError("UpdateProvider object must be used in a with statement")
        LOGGER.info("Copying override %s", override)
        fs.send_file(self.root / "overrides" / override, override)


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
                requests.get(
                    self.url._replace(
                        path=str(self.path / "pack-manifest.json")
                    ).geturl()
                ).content
            )
        except Exception as err:
            LOGGER.debug("Exception: %s", utils.err_str(err))
            raise ValueError("URL is invalid, it doesn't have a pack-manifest.json")
        self.mod_map = {mod["addonID"]: mod for mod in self.manifest["mods"]}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def get_manifest(self):
        return self.manifest

    def install_mod(self, fs: filesystem.common.FileSystem, addonID: str):
        mod = self.mod_map.get(addonID, None)
        if mod is None:
            LOGGER.error("Tryied to install invalid mod with id %s, skipping", addonID)
            return
        LOGGER.info("Downloading mod %s", mod.get("name", addonID))
        fs.download(
            network.TwitchAPI.get_download_url(addonID, mod["fileID"]),
            "mods/" + mod["filename"],
        )

    def install_override(self, fs: filesystem.common.FileSystem, override: str):
        LOGGER.info("Downloading override %s", override)
        fs.download(
            self.url._replace(path=str(self.path / "overrides" / override)).geturl(),
            override,
        )

class UpdateType(enum.Enum):
    LOCAL = (("local",), LocalUpdateProvider)
    HTTP = (("http",), HTTPUpdateProvider)

    def __new__(cls, aliases, function=None):
        obj = object.__new__(cls)
        obj._value_ = aliases[0]
        obj.aliases = aliases
        obj.function = function
        return obj

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)

    @classmethod
    def _missing_(cls, value):
        string = str(value).lower()
        for member in cls:
            if string in member.aliases:
                return member

class InstallType(enum.Enum):
    LOCAL = (("local",), filesystem.LocalFileSystem)
    FTP = (("ftp",), filesystem.FTPFileSystem.from_url)

    def __new__(cls, aliases, function=None):
        obj = object.__new__(cls)
        obj._value_ = aliases[0]
        obj.aliases = aliases
        obj.function = function
        return obj

    def __call__(self, *args, **kwargs):
        return self.function(*args, **kwargs)

    @classmethod
    def _missing_(cls, value):
        string = str(value).lower()
        for member in cls:
            if string in member.aliases:
                return member


def update(
    source,
    install,
    source_type: UpdateType,
    install_type: InstallType,
    packmodes
):
    UpdateProviderConstructor = UpdateType(source_type)
    FileSystemConstructor = InstallType(install_type)
    with FileSystemConstructor(install) as fs, UpdateProviderConstructor(source) as provider:
        return update_pack(provider, fs, packmodes)


def update_pack(
    update: UpdateProvider,
    fs: filesystem.common.FileSystem,
    packmodes: List[str] = None,
):
    """
    Performs a pack update

    Arguments
        update -- UpdateProvied object that will provide update files
        fs -- a filesystem object to the pack to update
    """
    LOGGER.info("Starting update")
    # Get local configuration
    LOGGER.info("Reading pack manifest")
    if fs.exists("pack-manifest.json"):
        with fs.open("pack-manifest.json") as f:
            local_manifest = manifest.pack.load(f)
        LOGGER.info(
            "Local version is %s with packmodes: %s",
            local_manifest["pack-version"],
            ", ".join(local_manifest.get("current-packmodes", ["No packmodes found"])),
        )
    else:
        if ui.confirm_install():
            local_manifest = manifest.pack.get_default()
        else:
            sys.exit(
                "User aborted update. In case this is before a modpack start, I'm crashing to prevent the start"
            )
    # Get remote configuration
    LOGGER.info("Reading update manifest")
    remote_manifest = update.get_manifest()
    # Verify packmodes
    if not packmodes:
        if "current-packmodes" in local_manifest:
            packmodes = local_manifest["current-packmodes"]
            LOGGER.info("No packmodes provided for update, using previous packmodes: %s", ", ".join(packmodes))
        else:
            packmodes = list(remote_manifest["packmodes"].keys())
            LOGGER.info("No packmodes provided for update, no previous packmodes, defaulting to all packmodes")
    # Compute states
    local_packmodes = manifest.pack.get_all_dependencies(
        local_manifest["packmodes"], local_manifest.get("current-packmodes", [])
    )
    new_packmodes = manifest.pack.get_all_dependencies(
        remote_manifest["packmodes"], packmodes
    )
    # Quick comparison
    if (
        remote_manifest["pack-version"] == local_manifest["pack-version"]
        and local_packmodes == new_packmodes
    ):
        LOGGER.info("Nothing to update !")
        return
    else:
        LOGGER.info(
            "Updating to version %s with packmodes: %s (includes dependencies)",
            remote_manifest["pack-version"],
            ", ".join(packmode for packmode in sorted(new_packmodes)),
        )
    # Update mods
    LOGGER.info("Updating mods")
    LOGGER.info("Comparing old and new states")
    mod_diff = common.compute_mod_diff(
        manifest.pack.get_selected_mods(local_manifest, local_packmodes),
        manifest.pack.get_selected_mods(remote_manifest, new_packmodes),
        loglevel=logging.DEBUG,
    )
    LOGGER.info("Applying mod difference")
    mod_dir = Path("mods")
    local_mod_map = {mod["addonID"]:mod for mod in local_manifest["mods"]}
    for addonID in mod_diff.deleted:
        mod = local_mod_map[addonID]
        LOGGER.info("Deleting mod %s", mod["name"])
        fs.unlink(mod_dir / mod["filename"])
    for addonID in mod_diff.updated:
        mod = local_mod_map[addonID]
        LOGGER.info("Deleting mod %s", mod["name"])
        fs.unlink(mod_dir / mod["filename"])
        update.install_mod(filesystem, addonID)
    for addonID in mod_diff.added:
        update.install_mod(fs, addonID)

    # Update overrides
    LOGGER.info("Updating overrides")
    LOGGER.info("Comparing old and new states")
    override_diff = common.compute_override_diff(
        manifest.pack.get_selected_overrides(local_manifest, local_packmodes),
        manifest.pack.get_selected_overrides(remote_manifest, new_packmodes),
        loglevel=logging.DEBUG,
    )
    LOGGER.info("Applying override difference")
    # remote_url = manifest_url._replace(path=str(Path(manifest_url.path).parent))
    # remote_path = Path(remote_url.path)
    for override in override_diff.deleted:
        LOGGER.info("Deleting override %s", override)
        fs.unlink(override)
    for override in override_diff.updated:
        LOGGER.info("Deleting override %s", override)
        fs.unlink(override)
        update.install_override(fs, override)
    for override in override_diff.added:
        update.install_override(fs, override)
    # Write new manifest to save current state
    new_manifest = manifest.pack.copy(
        remote_manifest,
        current_packmodes=list(packmodes)
    )
    with fs.open("pack-manifest.json", "wt") as f:
        manifest.pack.dump(new_manifest, f, encode=False)
    LOGGER.info("Done !")
