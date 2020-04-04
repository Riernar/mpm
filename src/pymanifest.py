# standard library
from typing import List, Mapping, Iterable, Union
from pathlib import Path
import json
from copy import deepcopy

# third parties
import jsonschema

# local import
from . import utils

MANIFEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "definitions": {
        # Definition for a mod
        "mod": {
            "type": "object",
            "properties": {
                "addonID": {"type": "integer"},
                "fileID": {"type": "integer"},
                "packmode": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["addonID", "fileID", "packmode"],
            "additionalProperties": False,
        },
        # Definition for a cached override
        "cached-override": {
            "type": "object",
            "properties": {"filepath": {"type": "string"}, "hash": {"type": "string"}},
            "required": ["filepath", "hash"],
            "additionalProperties": False,
        },
    },
    "type": "object",
    "properties": {
        # version of the pack, of the form 'XX.XX.XX'
        "pack-version": {"type": "string", "pattern": "^[0-9]+[.][0-9]+[.][0-9]+$"},
        # dependencies between packmodes
        # A Mapping from a packmode name to a list of its parents
        # Names must be lowercase letters, with "-" allowed
        # Name must not be 'server'
        "packmodes": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
            "propertyNames": {
                "allOf": [{"not": {"pattern": "^server$"}}, {"pattern": "[a-z-]+"}]
            },
        },
        # Current packmode
        # Should be "server" or one of the packmode defined above
        # But i couldn't find how to express that in json-schema
        "current-packmodes": {"type": "array", "items": {"type": "string"}},
        # URL for the overrides (i.e. the .zip file outputed by curse)
        "overrides-url": {"type": "string", "format": "uri"},
        # The list of mods, a list of object with exactly
        # the properties [addonID, fileID, packmode]
        "mods": {"type": "array", "items": {"$ref": "#/definitions/mod"}},
        # The overrides packmodes assigments
        "overrides": {
            "type": "object",
            "additionalProperties": {"type": "string"}
            ## TODO: Path regex && match key pattern to string type
        },
        # The cache for overrides
        "overrides-cache": {
            "type": "array",
            "item": {"$ref": "#/definitions/cached-override"},
        },
    },
    "required": ["pack-version", "packmodes", "mods", "overrides-cache",],
    "additionalProperties": False,
}


DEFAULT_MANIFEST = {
    "pack-version": "0.0.0",
    "packmodes": {},
    "overrides-url": "",
    "mods": [],
    "overrides": [],
    "overrides-cache": [],
}


def get_default_manifest():
    """
    Returns a new default manifest in JSON
    """
    return deepcopy(DEFAULT_MANIFEST)


class BaseManifestError(Exception):
    """
    Base manifest error
    """


class CircularDependencyError(utils.AutoFormatError, BaseManifestError):
    """
    Exception for circular dependency in packmodes

    Attributes
        cycle -- cycle that triggered the error
        message -- error explanation (auto-formatted, see AutoFormatError base class)
    """

    def __init__(self, cycle, message="Circular dependency in packmodes: {cycle}"):
        super().__init__(message)
        self.cycle = cycle
        self.message = message


class UndefinedDependencyError(utils.AutoFormatError, BaseManifestError):
    """
    Exception for packmode depending on undefined packmode

    Attributes
        packmode -- offending packmode
        dependency -- undefined dependency
        message -- error explanation (auto-formatted, see AutoFormatError base class)
    """

    def __init__(
        self,
        source,
        dependency,
        message="Packmode {source} depends on {dependency} which is not defined",
    ):
        super().__init__(message)
        self.source = source
        self.dependency = dependency


class UndefinedPackmodeError(utils.AutoFormatError, BaseManifestError):
    """
    Exception for undefined packmode

    Attributes
        packmode -- undefined packmode
        source -- what is trying to use the undefined packmode
        message -- error explanation (auto-formatted, see AutoFormatError base class)
    """

    def __init__(self, packmode, source=None, message="{packmode} is undefined"):
        super().__init__(message)
        self.source = source
        self.packmode = packmode


def validate_dependencies(packmode_dependencies: Mapping[str, Iterable[str]]):
    """
    Validate packmode definitions

    Arguments
        packmode_dependencies -- mapping from packmode names to list of dependencies
            all packmode implicitely depends on "server"
    
    Raise
        CircularDependencyError -- there is a circular dependency in the packmodes
        InvalidDependencyError -- a packmode depends on an undefined packmode
    """
    all_packmodes = packmode_dependencies.keys() | {"server"}
    graph = {packmode: [] for packmode in all_packmodes}
    for packmode, dependencies in packmode_dependencies.items():
        for dep in set(dependencies) | {"server"}:
            if dep not in all_packmodes:
                raise UndefinedDependencyError(packmode, dep)
            graph[dep].append(packmode)
    try:
        utils.dfs(graph, "server")
    except utils.CycleDFSError as err:
        raise CircularDependencyError(cycle=err.cycle)


def validate_packmodes(pack_manifest):
    """
    Validates overrides' and mods' packmode are defined
    Arguments
        pack_manifest -- a json that follows the MANIFEST_SCHEMA schema
    Returns
        None
    Raise
        jsonschema.ValidationError if the packmodes are invalid
    """
    all_packmodes = pack_manifest["packmodes"].keys() | {"server"}
    for mod in pack_manifest["mods"]:
        if mod["packmode"] not in all_packmodes:
            raise jsonschema.ValidationError(
                "Mod with ID '%s' has undefined packmode '%s'"
                % (mod["addonID"], mod["packmode"])
            )
    for override, packmode in pack_manifest["overrides"].items():
        if packmode not in all_packmodes:
            raise jsonschema.ValidationError(
                "Override '%s' has undefined packmode '%s'" % (override, packmode)
            )
    graph = {packmode: set() for packmode in all_packmodes}
    for packmode, parents in pack_manifest["packmodes"].items():
        if packmode == "server":
            raise jsonschema.ValidationError(
                "Packmode 'server' cannot have dependencies"
            )
        for dependency in set(parents) | {"server"}:
            pass


def validate_manifest(pack_manifest):
    jsonschema.validate(instance=pack_manifest, schema=MANIFEST_SCHEMA)
    validate_dependencies(pack_manifest["packmodes"])
    validate_packmodes(pack_manifest)


def read_manifest_file(filepath: Path):
    """
    Retrieve a manifest

    Arguments
        filepath -- path to the manifest file
    """
    filepath = Path(filepath)
    with filepath.open() as f:
        pack_manifest = json.load(f)
    validate_manifest(pack_manifest)
    return pack_manifest


def get_override_packmode(
    overrides: Mapping[str, str], relpath: str
) -> Union[str, None]:
    """
    Returns the packmode of an override file as defined in 'overrides'. Packmode
        for overrides are defined in a bottom-up manner: specific
        packmode for a file override the assignement of its parent
        folder

    Arguments
        overrides -- overrides assignement to packmode
        relpath -- relative path to override file starting from "minecraft/"
            (.e.g, modes convig are of the form 'config/modname.cfg')
    
    Returns
        The packmode for that override, or None
    """
    relpath = Path(relpath)
    if str(relpath) in overrides:
        return overrides[str(relpath)]
    else:
        for i in range(len(relpath.parents)):
            key = str(relpath.parents[i])
            if key in overrides:
                return overrides[key]
