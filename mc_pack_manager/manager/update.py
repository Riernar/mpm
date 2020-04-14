"""
Update management module

Part of the Minecraft Pack Manager utility (mpm)
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union
import ftplib
import hashlib
import tempfile
import requests

PathLike = Union[str, Path]

class FileSystem(ABC):
    def __init__(self):
        pass

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
    def download_file(self, url: str, dest: PathLike):
        """
        dowload a file from the web
        """

    @abstractmethod
    def get_file(self, path: PathLike):
        """
        get a file object
        compliant with the "with ... as ...:" syntax
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

    def download_file(self, url: str, dest: PathLike):
        dest = self.base_dir / Path(dest)
        r = requests.get(url)
        with dest.open('w') as f:
            f.write(r.text)

    def get_file(self, path: PathLike):
        path = self.base_dir / Path(path)
        return path.open('r')

class FTPFileSystem(FileSystem):
    def __init__(self, host: str, user: str, passwd: str, base_dir: PathLike):
        self.ftp = ftplib.FTP(host)
        self.ftp.login(user = user, passwd = passwd)
        self.base_dir = Path(base_dir)
        try:
            self.ftp.cwd(self.base_dir.as_posix())
        except ftplib.error_perm:
            raise RuntimeError

    def _exists(self, path: Path):
        #check if folder or file exists
        return (path == Path('.')) or (path.name in self.ftp.nlst(path.parent.as_posix()))

    def _is_dir(self, path: Path):
        if not self._exists(path):
            raise RuntimeError
        return (path == Path('.')) or (path.name in self.ftp.nlst(path.parent.as_posix()))

    def _send_file(self, file: Path, dest: Path):
        if not self._exists(dest.parent):
            # check if destination directory exists
            raise RuntimeError
        if self._exists(dest):
            # The file already exists, it should better not be overriten!
            raise RuntimeError
        if not file.is_file():
            raise RuntimeError
        self.ftp.storbinary('STOR '+dest.as_posix(), file.open('rb'))

    def _send_folder(self, folder: Path, dest: Path):
        """
        send the folder onto the ftp server on the destination dir dest
        """
        if not self._exists(dest):
            # The destination folder is inexistant!
            raise RuntimeError
        if self._exists(dest / folder.name):
             # The folder already exists, it should better not be overriten!
             raise RuntimeError
        if not folder.is_dir():
            raise RuntimeError
        #create folder
        self.ftp.mkd((dest / folder.name).as_posix())
        for elt in folder.iterdir():
            elt_dest = dest / folder.name / elt.relative_to(folder)
            if elt.is_file():
                self._send_file(elt, elt_dest)
            else:
                self._send_folder(elt, elt_dest)

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
            self.ftp.cwd(path.as_posix()) #fails if not a dir
        except ftplib.error_perm:
            #fallback if it is a file
            self.delete_file(path)
            return
        #here it is a dir
        for elt in self.ftp.nlst("."):
            elt = Path(elt)
            print(elt)
            self._sub_delete_folder(elt)
        self.ftp.cwd("..")
        self.ftp.rmd(path.as_posix())

    def move_file(self, path: PathLike, dest: PathLike):
        path = Path(path)
        dest = Path(dest)
        if self._exists(path):
            self.ftp.rename(path.as_posix(), dest.as_posix())

    def download_file(self, url: str, dest: PathLike):
        dest = Path(dest)
        with tempfile.TemporaryDirectory(dir=".") as tmp_dir:
            r = requests.get(url)
            tmp_file_name = Path(hashlib.sha256(str.encode(url)).hexdigest()[:20])
            tmp_file = tmp_dir / tmp_file_name
            with tmp_file.open('w') as f:
                f.write(r.text)
            self._send_file(tmp_file, dest)

    def get_file(self, path: PathLike):
        path = Path(path)
        tmp = []
        self.ftp.retrlines('RETR ' + path.as_posix(), lambda data: tmp.append(data))
        return "".join(tmp)

    def get_file_test(self, path: PathLike):
        path = Path(path)
        tmp = tempfile.NamedTemporaryFile(dir='.')
        self.ftp.retrbinary('RETR ' + path.as_posix(), lambda data: tmp.file.write(data))
        tmp.flush()
        return open(tmp.name, 'r')

def update_pack():
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
    """
    raise NotImplementedError
