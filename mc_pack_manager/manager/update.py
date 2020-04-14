"""
Update management module

Part of the Minecraft Pack Manager utility (mpm)
"""

from pathlib import Path
from typing import Union


PathLike = Union[str, Path]



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
