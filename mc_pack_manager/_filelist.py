"""
List of files that are part of MPM implementation

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
import inspect
from pathlib import Path

MPM_SRC_DIR = Path(inspect.getfile(inspect.currentframe())).absolute().parent
MPM_SRC_FILES = tuple(
    MPM_SRC_DIR / filepath
    for filepath in (
        "filesystem/__init__.py",
        "filesystem/common.py",
        "filesystem/ftp.py",
        "filesystem/local.py",
        "manager/__init__.py",
        "manager/common.py",
        "manager/release.py",
        "manager/snapshot.py",
        "manager/update.py",
        "manifest/__init__.py",
        "manifest/common.py",
        "manifest/curse.py",
        "manifest/pack.py",
        "ui/__init__.py",
        "ui/packmodes.py",
        "ui/widgets.py",
        "__init__.py",
        "_filelist.py",
        "network.py",
        "utils.py",
    )
)
