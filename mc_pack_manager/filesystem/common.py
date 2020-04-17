"""
Common code for filesystem utilities

Part of the Minecraft Pack Manager utility (mpm)
"""

# Standard Library imports
from abc import ABC, abstractmethod
from functools import wraps
import logging
from pathlib import PurePath
import tempfile
from typing import Union

# Local imports
from .. import utils

PathLike = Union[str, PurePath]
Mode = Union["b", "t"]

LOGGER = utils.getLogger(__name__)

class FileSystemBaseError(Exception):
    """
    Base error for filesystem operation
    """

class InvalidURL(FileSystemBaseError, utils.AutoFormatError):
    """
    The URL is not an FTP url
    """
    def __init__(self, url, fstype, message="{url} is invalid for a {fstype} filesystem"):
        super().__init__(message)
        self.url = url
        self.fstype = fstype
        self.message = message

class FileSystem(ABC):
    """
    Class for abstracting a filesystem, local or remote with various
    connexion protocols, into a single object
    """
    def __init__(self, base_dir: PathLike):
        super().__init__()
        self.base_dir = PurePath(base_dir)

    def __enter__(self):
        """
        Context manager implementation
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager implementation
        """
        self.close()
    
    @abstractmethod
    def close(self):
        """
        Clean up resources
        """

    @abstractmethod
    def exists(self, path: PathLike):
        """
        Determines if the path points to something

        Arguments
            path -- path to test the existence of, relative to base_dir
        
        Return
            True if the path exists, False, otherwise
        """
    
    @abstractmethod
    def is_file(self, path: PathLike):
        """
        Tests if a path is a file. Returns false if the path doesn't exists

        Arguments
            path -- path from base_dir to test
        
        Returns
            True if the relative path exists and is a file, false otherwise
        """

    @abstractmethod
    def is_dir(self, path: PathLike):
        """
        Tests if a path is a directory. Returns false if the path doesn't exist

        Arguments
            path -- path from base_dir to test

        Returns
            True if the relative path exists and is a directory, false otherwise
        """

    @abstractmethod
    def unlink(self, path: PathLike):
        """
        Deletes a file

        Arguments
            path -- path relative to base_dir to delete
        """

    @abstractmethod
    def rmdir(self, path: PathLike):
        """
        Recursively deletes a folder

        Arguments
            path -- path relative to base_dir of the folder to delete
        """

    @abstractmethod
    def move_file(self, path: PathLike, dest: PathLike, force:bool=False):
        """
        Moves a file

        Arguments
            path -- file to move
            dest -- new name
            force -- overwrite destination if it already exists
        """

    @abstractmethod
    def download(self, url: str, dest: PathLike, force:bool=False):
        """
        Downloads a file from the web into the filesystem

        Arguments
            url -- url of the file to download
            dest -- destination file
            force -- overwrite destination file if it exists
        """

    @abstractmethod
    def send_data(self, fp, dest: PathLike, force:bool=False):
        """
        Sends the content of a filelike object to dest

        Arguments
            f -- file-like object to send the data from
            dest -- destination file
            force -- overwrite dest if it exists
        """

    @abstractmethod
    def send_file(self, src: PathLike, dest: PathLike, force:bool=False):
        """
        Sends a local file to the filesystem

        Arguments
            src -- local path to send
            dest -- destination file
            force -- overwrite dest if it exists
        """

    @abstractmethod
    def send_dir(self, src: PathLike, dest: PathLike, force:bool=False):
        """
        Sends a local directory to the filesystem

        Arguments
            src -- local path to send
            dest -- destination file
            force -- overwrite dest if it exists
        """

    @abstractmethod
    def open(self, path: PathLike, mode: str):
        """
        Open a file on the filesystem

        Arguments
            path -- path to open relative to base_dir
            mode -- open mode. See built-ins open(). Might be ignored
        """



class RemoteFileObject:
    """
    File-like object to open a remote file and then synchronize it
    """
    def __init__(self, fs: FileSystem, remote_path: PathLike, tmp: tempfile.TemporaryFile):
        self.fs = fs
        self.tmp = tmp
        self.remote_path = remote_path

    def __enter__(self):
        self.tmp.__enter__()
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.tmp.flush()
        self.tmp.seek(0)
        self.fs.send_data(self.tmp, self.remote_path, force=True)
        self.tmp.__exit__(exc_type, exc_value, traceback)
    
    def close(self):
        self.tmp.flush()
        self.tmp.seek(0)
        self.fs.send_data(self.tmp, self.remote_path, force=True)
        self.tmp.close()
    
    def write(self, *args, **kwargs):
        self.tmp.write(*args, **kwargs)
    
    def read(self, *args, **kwargs):
        self.tmp.read(*args, **kwargs)
    
    def seek(self, *args, **kwargs):
        self.tmp.seek(*args, **kwargs)
    
    def flush(self, *args, **kwargs):
        self.tmp.flush(*args, **kwargs)
    
    def readlines(self, *args, **kwargs):
        self.tmp.readlines(*args, **kwargs)