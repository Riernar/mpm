"""
Curse manifest module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
import json
import logging
from pathlib import Path
from typing import Union

# Local import
from .. import utils
from ..manifest import common

LOGGER = logging.getLogger("mpm.manifest.curse")

PathLike = Union[str, Path]


class UnhandledCurseManifestVersion(utils.AutoFormatError, common.BaseManifestError):
    """
    Exception for unknown curse manifest version

    Attributes
        version -- unhandled version or None if version was not found
        message -- error explanation (auto-formatted, see AutoFormatError base class)
    """

    def __init__(
        self,
        version,
        message="Can handle manifest version {version} for curse manifest file",
    ):
        super().__init__(message)
        self.version = version


def read(filepath: PathLike):
    """
    Read a curse manifest file

    Arguments:
        filepath -- file to the json manifest to read
    """
    filepath = Path(filepath)
    LOGGER.info("Reading curse manifest file %s", filepath)
    with filepath.open() as f:
        curse_manifest = json.load(f)
    if curse_manifest.get("manifestVersion") != 1:
        raise UnhandledCurseManifestVersion(curse_manifest.get("manifestVersion"))
    return curse_manifest


def write(curse_manifest, filepath: PathLike):
    """
    Write a curse manifest into a file

    Arguments
        curse_manifest -- manifest to write
        filepath -- file to write into
    """
    with Path(filepath).open("w") as f:
        json.dump(curse_manifest, f, indent=4)


def dump(curse_manifest, filelike):
    """
    Dump a curse manifest as bytes into a file-like object (supporting write()).
    The encoding is utf-8

    Arguments
        curse_manifest -- curse manifest to dump
        filelike -- filelike object that has a write() method
    """
    filelike.write(json.dumps(curse_manifest, indent=4).encode("utf-8"))
