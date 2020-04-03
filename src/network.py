import json
import logging
import requests


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
        return requests.get(*args, headers=cls.HEADERS, **kwargs)

    @classmethod
    def get_addon_info(
        cls, addonID, logger: logging.Logger = None, loglevel=logging.debug
    ):
        """
        Get a Twitch addon info as a JSON file

        Args:
            addonID : the ID of the addon, as found in manifest files
        
        Returns:
            A json object (as built by the `json` module) containing the info for the addon
        """
        if addonID not in cls.MOD_CACHE:
            if logger:
                logger.log(loglevel, "Downloading info for addon %s", addonID)
            req = cls.get(f"{cls.ROOT}/addon/{addonID}")
            cls.MOD_CACHE[addonID] = json.loads(req.content)
            return cls.MOD_CACHE[addonID]
        else:
            if logger:
                logger.log(loglevel, "Using cached info for addon %s", addonID)
            return cls.MOD_CACHE[addonID]

    @classmethod
    def get_file_info(
        cls, addonID, fileID, logger: logging.Logger = None, loglevel=logging.debug
    ):
        """
        Get a Twitch addon specific file information, as JSON
        """
        key = "%s/%s" % (addonID, fileID)
        if key not in cls.FILE_CACHE:
            if logger:
                logger.log(loglevel, "Downloding file info for file %s", key)
            req = cls.get(f"{cls.ROOT}/addon/{addonID}/file/{fileID}")
            cls.FILE_CACHE[key] = json.loads(req.content)
            return cls.FILE_CACHE[key]
        else:
            if logger:
                logger.log(loglevel, "Using cached info for file %s", key)
            return cls.FILE_CACHE[key]
