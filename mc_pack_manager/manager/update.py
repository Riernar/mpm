"""
Update management module

Part of the Minecraft Pack Manager utility (mpm)
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union
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
    def __init__(self, base_folder: PathLike):
        super().__init__()
        self.base_folder = base_folder

    def delete_file(self, path: PathLike):
        path = self.base_folder / Path(path)
        path.unlink()

    def delete_folder(self, path: PathLike):
        path = self.base_folder / Path(path)
        for elt in path.iterdir():
            if elt.is_file():
                elt.unlink()
            else:
                self.delete_folder(elt)
        path.rmdir()

    def move_file(self, path: PathLike, dest: PathLike):
        path = self.base_folder / Path(path)
        dest = self.base_folder / Path(dest)
        path.rename(dest)

    def download_file(self, url: str, dest: PathLike):
        dest = self.base_folder / Path(dest)
        r = requests.get(url)
        with dest.open('w') as f:
            f.write(r.text)

    def get_file(self, path: PathLike):
        path = self.base_folder / Path(path)
        return path.open('r')

class FTPFileSystem(FileSystem):
    def __init__(self, home):
        pass

    def delete_file(self, path: PathLike):
        raise NotImplementedError

    def delete_folder(self, path: PathLike):
        raise NotImplementedError

    def move_file(self, path: PathLike, dest: PathLike):
        raise NotImplementedError

    def download_file(self, url: str, dest: PathLike):
        raise NotImplementedError

    def get_file(self, path: PathLike):
        raise NotImplementedError


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
