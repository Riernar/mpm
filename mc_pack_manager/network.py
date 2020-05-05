"""
Part of the Minecraft Pack Manager utility (mpm)

Module handling network interactions
"""
# Standard lib import
import json
import logging
import requests

# Local import
from . import utils

LOGGER = logging.getLogger("mpm.network")


class TwitchAPI:
    """
    Class for connecting to the Twitch (CurseForge) API and caching results. See
    https://twitchappapi.docs.apiary.io/
    """

    ROOT = r"https://addons-ecs.forgesvc.net/api/v2"
    HEADERS = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Safari/537.36"
    }
    MOD_CACHE = {}
    FILE_CACHE = {}

    @classmethod
    def get(cls, *args, **kwargs):
        return urlget(*args, headers=cls.HEADERS, **kwargs)

    @classmethod
    def get_addon_info(cls, addonID):
        """
        Get a Twitch addon info as a JSON file

        Args:
            addonID : the ID of the addon, as found in manifest files
        
        Returns:
            A json object (as built by the `json` module) containing the info for the addon
        """
        if addonID not in cls.MOD_CACHE:
            LOGGER.debug("Downloading info for addon %s", addonID)
            req = cls.get(f"{cls.ROOT}/addon/{addonID}")
            cls.MOD_CACHE[addonID] = json.loads(req.content)
            return cls.MOD_CACHE[addonID]
        else:
            LOGGER.debug("Using cached info for addon %s", addonID)
            return cls.MOD_CACHE[addonID]

    @classmethod
    def get_file_info(cls, addonID, fileID):
        """
        Get a Twitch addon specific file information, as JSON
        """
        key = "%s/%s" % (addonID, fileID)
        if key not in cls.FILE_CACHE:
            LOGGER.debug("Downloding file info for file %s", key)
            try:
                cls.FILE_CACHE[key] = json.loads(
                    cls.get(f"{cls.ROOT}/addon/{addonID}/file/{fileID}").content
                )
            except json.JSONDecodeError as err:
                LOGGER.warn(
                    "Decoding received json failed, trying again in case of network problem"
                )
                LOGGER.debug(
                    "On addon %s/%s raised %s", addonID, fileID, utils.err_str(err)
                )
                cls.FILE_CACHE[key] = json.loads(
                    cls.get(f"{cls.ROOT}/addon/{addonID}/file/{fileID}").content
                )
            return cls.FILE_CACHE[key]
        else:
            LOGGER.debug("Using cached info for file %s", key)
            return cls.FILE_CACHE[key]

    @classmethod
    def get_download_url(cls, addonID, fileID):
        """
        Get a Twitch addon download url
        """
        key = "%s/%s" % (addonID, fileID)
        if key in cls.FILE_CACHE:
            LOGGER.debug("Using cached info for file %s for download url", key)
            return cls.FILE_CACHE[key]["downloadUrl"]
        else:
            LOGGER.debug("Retrieving download url for %s", key)
            return cls.get(
                f"{cls.ROOT}/addon/{addonID}/file/{fileID}/download-url"
            ).content


def urlget(*args, **kwargs):
    try:
        return urlget(*args, **kwargs)
    except Exception as err:
        LOGGER.warn(
            "A web request failed, trying again in case this is a network problem"
        )
        LOGGER.debug(
            "error is %s\n  args: %s\n  kwargs: %s", utils.err_str(err), args, kwargs,
        )
        return urlget(*args, **kwargs)
