"""
Part of the Minecraft Pack Manager utility (mpm)

Module handling network interactions
"""
# Standard lib import
import json
import logging
import requests
from time import sleep

# Local import
from . import utils

LOGGER = logging.getLogger("mpm.network")


class TwitchAPI:
    """
    Class for connecting to the Twitch (CurseForge) API and caching results. See
    https://twitchappapi.docs.apiary.io/
    """

    ROOT = r"https://addons-ecs.forgesvc.net/api/v2"
    #ROOT= r"https://private-anon-d0ed3247cf-twitchappapi.apiary-proxy.com/api/v2/"
    HEADERS = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.157 Safari/537.36"
    }
    MOD_CACHE = {}
    FILE_CACHE = {}
    SERVER_ERROR_RETRY_LIMIT = 10

    @classmethod
    def get(cls, *args, **kwargs):
        return cls.urlget(*args, headers=cls.HEADERS, **kwargs)

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
            try:
                req = cls.get(f"{cls.ROOT}/addon/{addonID}")
                cls.MOD_CACHE[addonID] = json.loads(req.content)
            except json.JSONDecodeError as err:
                LOGGER.warn(
                    "Decoding received JSON failed, trying again in case of network problem"
                )
                LOGGER.debug(
                    "While resolving %s, encountered: %s", addonID, utils.err_str(err)
                )
                LOGGER.debug("HTTP status code was %s", req.status_code)
                cls.MOD_CACHE[addonID] = json.loads(cls.get(f"{cls.ROOT}/addon/{addonID}").content)
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
                req = cls.get(f"{cls.ROOT}/addon/{addonID}/file/{fileID}")
                cls.FILE_CACHE[key] = json.loads(
                    req.content
                )
            except json.JSONDecodeError as err:
                LOGGER.warn(
                    "Decoding received JSON failed, trying again in case of network problem"
                )
                LOGGER.debug(
                    "While resolving %s/%s, encountered: %s", addonID, fileID, utils.err_str(err)
                )
                LOGGER.debug("HTTP status code was %s", req.status_code)
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

    @classmethod
    def urlget(cls, *args, **kwargs):
        count = 0
        while True:
            try:
                req = requests.get(*args, **kwargs)
                count += 1
            except Exception as err:
                LOGGER.debug(f"A web request raised on trials {count +1}: {utils.err_str(err)}")
                LOGGER.debug("Retrying")
            if req.ok or count >= cls.SERVER_ERROR_RETRY_LIMIT:
                break
            LOGGER.debug("Got HTTP status %s, trying again", req.status_code)
            LOGGER.debug("HTTP Headers were:\n%s", json.dumps(req.headers, indent=4))
            sleep(0.25) # to not be too aggressive with connexions
        if not req.ok:
            LOGGER.fatal("A web request failed %s time, check your network and the server", cls.SERVER_ERROR_RETRY_LIMIT)
            LOGGER.debug("HTTP response code: %s", req.status_code)
            LOGGER.debug("Headers:\n%s", json.dumps(req.headers, indent=4))
        return req
