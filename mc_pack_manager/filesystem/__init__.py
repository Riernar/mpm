"""
FileSytem package - abstract update process to work remotely

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library imports
import logging
import urllib.parse

# Local imports
from .. import utils
from ..filesystem.common import FileSystemBaseError
from ..filesystem.local import LocalFileSystem
from ..filesystem.ftp import FTPFileSystem

LOGGER = utils.getLogger(__name__)

class UnhandledURLError(FileSystemBaseError, utils.AutoFormatError):
    """
    Exception for url that cannot be converted to a FileSystem object
    """
    def __init__(self, url, message="No valid filesystem for url '{url}'"):
        super().__init__(message)
        self.url = url
        self.message = message

def get_filesystem(fs_root: str):
    """
    Retruns an appropriate filesystem object from a path or an url

    Arguments
        target -- the filesystem root. Can be
            + an local Path
            + an FTP url
    """
    url = urllib.parse.urlparse(fs_root)
    if url.scheme == "" and url.netloc == "":
        LOGGER.info("Connecting to local filesystem")
        return LocalFileSystem(url.path)
    elif url.scheme in  ("ftp", "sftp"):
        LOGGER.info(
            "Connecting to remote filesystem over ftp %s TLS",
            "with" if url.scheme == "sftp" else "*WITHOUT*"
        )
        return FTPFileSystem.from_url(fs_root)