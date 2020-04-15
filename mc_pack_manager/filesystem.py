"""
Part of the Minecraft Pack Manager utility (mpm)

Module handling filesystem I/O for updates
"""
# Standard Library imports
from abc import ABC, abstractmethod
import ftplib
import hashlib
import logging
from pathlib import Path
import requests
import shutil
import tempfile
from typing import Union
from urllib.parse import ParseResult

# Local imports
from . import utils

PathLike = Union[str, Path]
ReadMode = Union["b", "t"]

LOGGER = logging.getLogger("mpm.filesystem")

class BaseFilesystemError(Exception):
    """
    Base error for filesystem operation
    """

class UnhandledURLError(BaseFilesystemError, utils.AutoFormatError):
    """
    Exception for url that cannot be converted to a FileSystem object
    """
    def __init__(self, url, message="No valid filesystem for url '{url}'"):
        super().__init__(message)
        self.url = url
        self.message = message

class FTPPermissionError(BaseFilesystemError, utils.AutoFormatError):
    """
    Error for remote FTP filesystem with insufficient permissions
    """

    def __init__(self, err, err_str, message="Insufficient permissions: {err_str}"):
        super().__init__(message)
        self.message = message
        self.err = err


class FileSystem(ABC):
    @abstractmethod
    def __enter__(self):
        """
        Context manager implementation
        """

    @abstractmethod
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager implementation
        """

    @abstractmethod
    def delete_file(self, path: PathLike):
        """
        delete a file on the system
        """

    @abstractmethod
    def delete_folder(self, path: PathLike):
        """
        move a file on the system
        """

    @abstractmethod
    def move_file(self, path: PathLike, dest: PathLike):
        """
        move a file on the system
        """

    @abstractmethod
    def download_in(self, url: str, dest: PathLike):
        """
        dowload a file from the web
        """

    @abstractmethod
    def upload_file_in(self, src: PathLike, dest: PathLike):
        """
        Sends a local file to the filesystem
        """

    @abstractmethod
    def upload_folder_in(self, src: PathLike, dest: PathLike):
        """
        Sends a local folder to the filesystem
        """

    @abstractmethod
    def open(self, path: PathLike, mode: ReadMode = "b"):
        """
        get a file object that is a valid context manager
        The file is opened in mode "w+", and the byte or text part can be specified
        """


class LocalFileSystem(FileSystem):
    """
    Take as an argument the base_dir in which
    everything is done
    Path are thus relative to base_dir
    """

    def __init__(self, base_dir: PathLike):
        super().__init__()
        self.base_dir = base_dir

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def delete_file(self, path: PathLike):
        path = self.base_dir / Path(path)
        path.unlink()

    def delete_folder(self, path: PathLike):
        path = self.base_dir / Path(path)
        for elt in path.iterdir():
            if elt.is_file():
                elt.unlink()
            else:
                self.delete_folder(elt)
        path.rmdir()

    def move_file(self, path: PathLike, dest: PathLike):
        path = self.base_dir / Path(path)
        dest = self.base_dir / Path(dest)
        path.rename(dest)

    def download_in(self, url: str, dest: PathLike):
        dest = self.base_dir / Path(dest)
        r = requests.get(url)
        with dest.open("wb") as f:
            f.write(r.content)

    def upload_file_in(self, src: PathLike, dest: PathLike):
        src = self.base_dir / Path(src)
        dest = Path(dest)
        shutil.copyfile(src=src, dst=dest)

    def upload_folder_in(self, src: PathLike, dest: PathLike):
        src = self.base_dir / Path(src)
        dest = Path(dest)
        shutil.copytree(src=src, dst=dest)

    def open(self, path: PathLike, mode="t"):
        path = self.base_dir / Path(path)
        return path.open("w+" + mode)


class FTPFileSystem(FileSystem):
    def __init__(self, host: str, user: str, passwd: str, base_dir: PathLike, use_tls: bool = False):
        if use_tls:
            self.ftp = ftplib.FTP_TLS(host)
            self.ftp.login(user=user, passwd=passwd)
            self.ftp.prot_p()
        else:
            self.ftp = ftplib.FTP(host)
            self.ftp.login(user=user, passwd=passwd)
        self.base_dir = Path(base_dir)
        try:
            self.ftp.cwd(self.base_dir.as_posix())
        except ftplib.error_perm as err:
            raise FTPPermissionError(err=err, err_str=utils.err_str(err))
        self.tempdir = tempfile.TemporaryDirectory(dir=".")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Cleanup temporary directory
        self.tempdir.cleanup()

    def _exists(self, path: Path):
        # check if folder or file exists
        return (path == Path(".")) or (
            path.name in self.ftp.nlst(path.parent.as_posix())
        )

    def delete_file(self, path: PathLike):
        path = Path(path)
        self.ftp.delete(path.as_posix())

    def delete_folder(self, path: PathLike):
        path = Path(path)
        if self._exists(path):
            self.ftp.cwd(path.parent.as_posix())
            self._sub_delete_folder(path)
        self.ftp.cwd(self.base_dir.as_posix())

    def _sub_delete_folder(self, path: Path):
        try:
            self.ftp.cwd(path.as_posix())  # fails if not a dir
        except ftplib.error_perm:
            # fallback if it is a file
            self.delete_file(path)
            return
        # here it is a dir
        for elt in self.ftp.nlst("."):
            elt = Path(elt)
            self._sub_delete_folder(elt)
        self.ftp.cwd("..")
        self.ftp.rmd(path.as_posix())

    def move_file(self, path: PathLike, dest: PathLike):
        path = Path(path)
        dest = Path(dest)
        if self._exists(path):
            self.ftp.rename(path.as_posix(), dest.as_posix())
        else:
            raise FileNotFoundError(path)

    def download_in(self, url: str, dest: PathLike):
        with tempfile.TemporaryFile(dir=self.tempdir, mode="wb") as tmp_file:
            tmp_file.write(requests.get(url).content)
            self.upload_file_in(tmp_file.name, dest)

    def upload_file_in(self, src: PathLike, dest: PathLike):
        src = Path(src)
        dest = Path(dest)
        if not src.is_file():
            raise FileNotFoundError(src)
        if not self._exists(dest.parent):
            # check if destination directory exists
            raise NotADirectoryError(dest.parent)
        if self._exists(dest):
            # The file already exists, it should better not be overriten!
            raise FileExistsError(dest)
        with src.open("rb") as f:
            self.ftp.storbinary("STOR " + dest.as_posix(), f)

    def upload_folder_in(self, src: PathLike, dest: PathLike):
        src = Path(src)
        dest = Path(dest)
        if not self._exists(dest):
            # The destination folder is inexistant!
            raise RuntimeError
        if self._exists(dest / src.name):
            # The folder already exists, it should better not be overriten!
            raise RuntimeError
        if not src.is_dir():
            raise RuntimeError
        # create folder
        self.ftp.mkd((dest / src.name).as_posix())
        for elt in src.iterdir():
            elt_dest = dest / src.name / elt.relative_to(src)
            if elt.is_file():
                self.upload_file_in(elt, elt_dest)
            else:
                self.upload_folder_in(elt, elt_dest)

    def open(self, path: PathLike, mode: ReadMode = "b"):
        tmp_file = tempfile.TemporaryFile(dir=self.tempdir, mode="w+" + mode)
        self.ftp.retrbinary(
            "RETR " + path.as_posix(), lambda data: tmp_file.file.write(data)
        )
        tmp_file.flush()
        tmp_file.seek(0)
        return tmp_file



def get_filesystem(url: ParseResult):
    """
    Return the appropriate filesystem for a parsed url. Supported url:
        path only url, making a LocalFileSystem object
        ftp url, making a FTPFileSystem object
    """
    if url.scheme == "" and url.netloc == "":
        LOGGER.info("Connecting to local filesystem")
        return LocalFileSystem(url.path)
    elif url.scheme in  ("ftp", "sftp"):
        LOGGER.info("Connecting to remote filesystem over ftp")
        if url.scheme == "sftp":
            LOGGER.info("TLS is activated")
        else:
            LOGGER.info("TLS is *NOT* activated")
        return FTPFileSystem(
            host=url.hostname,
            user=url.username,
            passwd=url.password,
            base_dir=url.path,
            use_tls=url.scheme == "sftp"
        )
    else:
        raise UnhandledURLError(url=url.geturl())