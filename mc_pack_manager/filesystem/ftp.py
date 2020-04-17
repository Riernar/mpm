"""
Remote FTP filesystem implementation

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library imports
import ftplib
import logging
from pathlib import Path
import requests
import tempfile
import urllib.parse

# Local import
from .. import utils
from ..filesystem import common

LOGGER = utils.getLogger(__name__)

class FTPPermissionError(common.FileSystemBaseError, utils.AutoFormatError):
    """
    Error for remote FTP filesystem with insufficient permissions
    """

    def __init__(self, err, err_str, message="Insufficient permissions: {err_str}"):
        super().__init__(message)
        self.message = message
        self.err = err


class FTPFileSystem(common.FileSystem):
    """
    Represents a remote filesystem over FTP
    """

    def __init__(
        self,
        host: str,
        user: str,
        passwd: str,
        base_dir: common.PathLike,
        use_tls:bool=False
    ):
        """
        Creates a new filesystem object

        Arguments
            host -- remote FTP hostname
            user -- user to log with. Defaults to "anonymous" as per ftplib spec
            passwd -- pawwsord to log with. Defaults to '' or '@anonymous' as per ftplib spec
            base_dir -- remote directory to use as the base for this filesystem
            use_tls -- use a secured connexion and secure the transmitted data
        """
        super().__init__(base_dir)
        if use_tls:
            self.ftp = ftplib.FTP_TLS(host)
            self.ftp.login(user=user, passwd=passwd)
            self.ftp.prot_p()
        else:
            self.ftp = ftplib.FTP(host)
            self.ftp.login(user=user, passwd=passwd)
        try:
            self.ftp.cwd(self.base_dir.as_posix())
        except ftplib.error_perm as err:
            raise FTPPermissionError(err=err, err_str=utils.err_str(err))
        self.tempdir = tempfile.TemporaryDirectory(dir=".")

    
    @classmethod
    def from_url(cls, url: str):
        """
        Create a FTP filesystem from a URL

        Arguments
            url -- url to connect to
        """
        purl = urllib.parse.urlparse(url)
        if purl.scheme not in ("ftp", "sftp"):
            raise common.InvalidURL(url=url, fstype="ftp")
        return cls(
            host=purl.hostname,
            user=purl.username,
            passwd=purl.password,
            base_dir=purl.path,
            use_tls=purl.scheme == "sftp"
        )
    
    def close(self):
        """
        Clean up resources
        """
        self.ftp.quit()
        self.tempdir.cleanup()

    def exists(self, path: common.PathLike):
        """
        Determines if the path points to something

        Arguments
            path -- path to test the existence of, relative to base_dir
        
        Return
            True if the path exists, False, otherwise
        """
        try:
            self.ftp.sendcmd("MLST %s" % (self.base_dir / path).as_posix())
            return True
        except ftplib.error_perm as err:
            if "cannot be listed" in err.args[0]:
                return False
            raise
    
    def is_file(self, path: common.PathLike):
        """
        Tests if a path is a file. Returns false if the path doesn't exists

        Arguments
            path -- path from base_dir to test
        
        Returns
            True if the relative path exists and is a file, false otherwise
        """
        try:
            return "type=file" in self.ftp.sendcmd("MLST %s" % (self.base_dir / path).as_posix())
        except ftplib.error_perm as err:
            if "cannot be listed" in err.args[0]:
                return False
            raise

    def is_dir(self, path: common.PathLike):
        """
        Tests if a path is a directory. Returns false if the path doesn't exist

        Arguments
            path -- path from base_dir to test

        Returns
            True if the relative path exists and is a directory, false otherwise
        """
        try:
            return "type=dir" in self.ftp.sendcmd("MLST %s" % (self.base_dir / path).as_posix())
        except ftplib.error_perm as err:
            if "cannot be listed" in err.args[0]:
                return False
            raise

    def unlink(self, path: common.PathLike):
        """
        Deletes a file

        Arguments
            path -- path relative to base_dir to delete
        """
        if self.is_dir(path):
            raise IsADirectoryError(path)
        elif self.is_file(path):
            try:
                self.ftp.delete((self.base_dir / path).as_posix())
            except ftplib.error_perm as err:
                if "No such file or directory" in err.args[0]:
                    return
                raise FTPPermissionError(
                    err=err,
                    err_str=utils.err_str(err)
                )

    def rmdir(self, path: common.PathLike):
        """
        Recursively deletes a folder

        Arguments
            path -- path relative to base_dir of the folder to delete
        """
        if self.is_file(path):
            raise NotADirectoryError(path)
        elif self.is_dir(path):
            try:
                self.ftp.rmd((self.base_dir / path).as_posix())
            except ftplib.error_perm as err:
                if "No such file or directory" in err.args[0]:
                    return
                raise FTPPermissionError(
                    err=err,
                    err_str=utils.err_str(err)
                )


    def move_file(self, path: common.PathLike, dest: common.PathLike, force:bool=False):
        """
        Moves a file

        Arguments
            path -- file to move
            dest -- new name
            force -- overwrite destination if it already exists
        """
        posix_path = (self.base_dir / path).as_posix()
        posix_dest = (self.base_dir / dest).as_posix()
        if self.exists(dest):
            if force:
                self.unlink(dest)
            else:
                FileExistsError("%s exists, cannot move to that destination" % dest)
        if self.exists(path):
            self.ftp.rename(posix_path, posix_dest)
        else:
            raise FileNotFoundError("%s doesn't exist, cannot move it" % path)


    def download(self, url: str, dest: common.PathLike, force:bool=False):
        """
        Downloads a file from the web into the filesystem

        Arguments
            url -- url of the file to download
            dest -- destination file
            force -- overwrite destination file if it exists
        """
        if self.exists(dest):
            if force:
                self.unlink(dest)
            else:
                raise FileExistsError("%s exists, cannot doawnload in that destination" % dest)
        with tempfile.TemporaryFile(dir=self.tempdir) as tmp:
            tmp.write(requests.get(url).content)
            tmp.seek(0)
            self.ftp.storbinary(
                cmd="STOR %s" % (self.base_dir / dest).as_posix(),
                fp=tmp
            )


    def send_data(self, fp, dest: common.PathLike, force:bool=False):
        """
        Sends the content of a filelike object to dest

        Arguments
            f -- file-like object to send the data from
            dest -- destination file
            force -- overwrite dest if it exists
        """
        if self.exists(dest):
            if force:
                self.unlink(dest)
            else:
                raise FileExistsError("%s exists, cannot send data into it" % dest)
        self.ftp.storbinary(
            cmd="STOR %s" % (self.base_dir / dest).as_posix(),
            fp=fp
        )


    def send_file(self, src: common.PathLike, dest: common.PathLike, force:bool=False):
        """
        Sends a local file to the filesystem

        Arguments
            src -- local path to send
            dest -- destination file
            force -- overwrite dest if it exists
        """
        if self.exists(dest):
            if force:
                self.unlink(dest)
            else:
                raise FileExistsError("%s exists, cannot send file into it" % dest)
        with open(src, mode="rb") as f:
            self.ftp.storbinary(
                cmd="STOR %s" % (self.base_dir / dest).as_posix(),
                fp=f
            )

    def send_dir(self, src: common.PathLike, dest: common.PathLike, force:bool=False):
        """
        Sends a local directory to the filesystem

        Arguments
            src -- local path to send
            dest -- destination file
            force -- overwrite dest if it exists
        """
        src = Path(src)
        if not src.is_dir():
            raise NotADirectoryError("%s is not a directory, cannot send it" % src)
        if self.exists(dest):
            if force:
                self.rmdir(dest)
            else:
                raise FileExistsError("%s exists, cannot send dir into it" % dest)
        stack = [src]
        while stack:
            elem = stack.pop()
            if elem.is_dir():
                for subelem in elem.iterdir():
                    stack.append(subelem)
            elif elem.is_file():
                dst = self.base_dir / dest / elem.relative_to(src)
                with open(elem, mode="rb") as f:
                    self.ftp.storbinary(cmd="STOR %s" % dst.as_posix(), fp=f)

    def open(self, path: common.PathLike, mode: str):
        """
        Open a file on the filesystem

        Arguments
            path -- path to open relative to base_dir
            mode -- open mode. See built-ins open()
        """
        mode = "t" if "t" in mode else "b"
        tmp = tempfile.TemporaryFile(dir=self.tempdir, mode="w+" + mode)
        if mode == "b":
            self.ftp.retrbinary(
                cmd="RETR %s" % (self.base_dir / path).as_posix(),
                callback=lambda data: tmp.write(data)
            )
        elif mode == "t":
            self.ftp.retrlines(
                cmd="RETR %s" % (self.base_dir / path).as_posix(),
                callback=lambda data: tmp.write(data)
            )
        return common.RemoteFileObject(fs=self, remote_path=path, tmp=tmp)
