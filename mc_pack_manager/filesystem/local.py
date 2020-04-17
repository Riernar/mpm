"""
Local filesystem implementation

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
from pathlib import Path
import requests
import shutil

# Local imports
from .. import utils
from ..filesystem import common

LOGGER = utils.getLogger(__name__)


class LocalFileSystem(common.FileSystem):
    """
    Local filesystem class
    """

    def __init__(self, base_dir: common.PathLike):
        """
        Create a new local filesystem, rooted in base_dir

        Arguments
            base_dir -- root of the local filesystem
        """
        super().__init__(base_dir)
        self.base_dir = Path(base_dir)

    def close(self):
        """
        Clean up resources
        """
        # Nothing to do
        pass

    def exists(self, path: common.PathLike):
        """
        Determines if the path points to something

        Arguments
            path -- path to test the existence of, relative to base_dir
        
        Return
            True if the path exists, False, otherwise
        """
        return (self.base_dir / Path(path)).exists()

    def is_file(self, path: common.PathLike):
        """
        Tests if a path is a file. Returns false if the path doesn't exists

        Arguments
            path -- path from base_dir to test
        
        Returns
            True if the relative path exists and is a file, false otherwise
        """
        return (self.base_dir / Path(path)).is_file()

    def is_dir(self, path: common.PathLike):
        """
        Tests if a path is a directory. Returns false if the path doesn't exist

        Arguments
            path -- path from base_dir to test

        Returns
            True if the relative path exists and is a directory, false otherwise
        """
        return (self.base_dir / Path(path)).is_dir()

    def unlink(self, path: common.PathLike):
        """
        Deletes a file

        Arguments
            path -- path relative to base_dir to delete
        """
        path = self.base_dir / Path(path)
        path.unlink()

    def rmdir(self, path: common.PathLike):
        """
        Recursively deletes a folder

        Arguments
            path -- path relative to base_dir of the folder to delete
        """
        p = self.base_dir / Path(path)
        if p.is_file():
            raise NotADirectoryError("%s is not a directory" % path)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    def move_file(
        self, path: common.PathLike, dest: common.PathLike, force: bool = False
    ):
        """
        Moves a file

        Arguments
            path -- file to move
            dest -- new name
            force -- overwrite destination if it already exists
        """
        if not force and self.exists(dest):
            raise FileExistsError("%s exists, cannot move to that destination" % dest)
        path = self.base_dir / Path(path)
        dest = self.base_dir / Path(dest)
        path.rename(dest)

    def download(self, url: str, dest: common.PathLike, force: bool = False):
        """
        Downloads a file from the web into the filesystem

        Arguments
            url -- url of the file to download
            dest -- destination file
            force -- overwrite destination file if it exists
        """
        if not force and self.exists(dest):
            raise FileExistsError(
                "%s exists, cannot download in that destination" % dest
            )
        with (self.base_dir / Path(dest)).open("wb") as f:
            f.write(requests.get(url).content)

    def send_data(self, fp, dest: common.PathLike, force: bool = False):
        """
        Sends the content of a filelike object to dest

        Arguments
            f -- file-like object to send the data from
            dest -- destination file
            force -- overwrite dest if it exists
        """
        if not force and self.exists(dest):
            raise FileExistsError("%s exists, cannot send data into it" % dest)
        data = fp.read(1)
        if isinstance(data, str):
            mode = "t"
        elif isinstance(data, bytes):
            mode = "b"
        else:
            raise TypeError(
                "Filelike read() method returns type %s, which is neither str or bytes"
                % type(data)
            )
        with (self.base_dir / dest).open("w" + mode) as lf:
            lf.write(data)
            lf.write(fp.read())

    def send_file(
        self, src: common.PathLike, dest: common.PathLike, force: bool = False
    ):
        """
        Sends a local file to the filesystem

        Arguments
            src -- local path to send
            dest -- destination file
            force -- overwrite dest if it exists
        """
        if not force and self.exists(dest):
            raise FileExistsError("%s exists, cannot send file into it" % dest)
        src = Path(src)
        dest = Path(dest)
        shutil.copyfile(src=src, dst=dest)

    def send_dir(
        self, src: common.PathLike, dest: common.PathLike, force: bool = False
    ):
        """
        Sends a local directory to the filesystem

        Arguments
            src -- local path to send
            dest -- destination file
            force -- overwrite dest if it exists
        """
        src = Path(src)
        if self.exists(dest):
            if force:
                self.rmdir(dest)
            else:
                raise FileExistsError("%s exists, cannot send dir into it" % dest)
        if not src.is_dir():
            raise NotADirectoryError("%s is not a directory, cannot send it" % src)
        shutil.copytree(src=src, dst=self.base_dir / Path(dest))

    def open(self, path: common.PathLike, mode="t"):
        """
        Open a file on the filesystem

        Arguments
            path -- path to open relative to base_dir
            mode -- open mode. See built-ins open()
        """
        return open(self.base_dir / Path(path), mode)
