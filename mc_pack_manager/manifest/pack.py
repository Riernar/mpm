"""
Pack manifest module

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard library import
from copy import deepcopy
import json
import logging
from pathlib import Path
from typing import Iterable, List, Mapping, Union, Set

# Third party library import
import jsonschema

# Local import
from .. import utils
from ..manifest import common

PathLike = Union[str, Path]

LOGGER = logging.getLogger("mpm.manifest.pack")

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
                "filename": {"type": "string"},
            },
            "required": ["addonID", "fileID", "packmode"],
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
        # The list of mods, a list of object with exactly
        # the properties [addonID, fileID, packmode]
        "mods": {"type": "array", "items": {"$ref": "#/definitions/mod"}},
        # The overrides packmodes assigments
        "overrides": {
            "type": "object",
            "additionalProperties": {"type": "string"}
            ## TODO: Path regex for keys
        },
        # The cache for overrides
        # Maps filepath to hash of file
        "override-cache": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            ## TODO: Path regex for keys
        },
    },
    "required": ["pack-version", "packmodes", "mods", "overrides", "override-cache"],
    "additionalProperties": False,
}


DEFAULT_MANIFEST = {
    "pack-version": "0.0.0",
    "packmodes": {},
    "mods": [],
    "overrides": [],
    "override-cache": {},
}


class CircularDependencyError(utils.AutoFormatError, common.BaseManifestError):
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


class UndefinedDependencyError(utils.AutoFormatError, common.BaseManifestError):
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


class UndefinedPackmodeError(utils.AutoFormatError, common.BaseManifestError):
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
    
    Raises
        CircularDependencyError -- there is a circular dependency in the packmodes
        UndefinedDependencyError -- a packmode depends on an undefined packmode
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


def validate_packmode_assignments(pack_manifest):
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


def validate(pack_manifest):
    """
    Validates a manifest, raising an exception if the manifest is invalid

    Arguments
        pack_manifest -- pack manifest object to validate

    Raises
        jsonschema.ValidationError -- if the pack manifest doesn't follow the schema
        CircularDependencyError -- there is a circular dependency in the packmodes
        UndefinedDependencyError -- a packmode depends on an undefined packmode
    """
    try:
        jsonschema.validate(instance=pack_manifest, schema=MANIFEST_SCHEMA)
        validate_dependencies(pack_manifest["packmodes"])
        validate_packmode_assignments(pack_manifest)
    except Exception as err:
        LOGGER.debug("Pack manifest validation failed due to %s", utils.err_str(err))
        raise


def get_default(with_override_url: bool = False):
    """
    Returns a new default manifest in JSON
    """
    pack_manifest = deepcopy(DEFAULT_MANIFEST)
    pack_manifest["pack-version"] = utils.Version(pack_manifest["pack-version"])
    if with_override_url:
        pack_manifest["overrides-url"]: ""
    return pack_manifest


def read_from(dir_: Union[str, Path]):
    """
    Load the pack-manifest.json file from dir ro defaults to the default manifest

    Arguments
        dir -- the directory to load the manifest from
    
    Return
        The validated pack_manifest
    """
    LOGGER.info("Reading pack-manifest.json from %s", dir_)
    dir_ = Path(dir_)
    if not dir_.exists():
        raise FileNotFoundError(dir_)
    if dir_.is_file():
        raise NotADirectoryError(dir_)
    pack_manifest = dir_ / "pack-manifest.json"
    if pack_manifest.exists():
        return read(pack_manifest)
    else:
        LOGGER.info("'pack-manifest.json' not found, using default manifest file")
        return get_default()


def read(filepath: PathLike):
    """
    Retrieve a manifest

    Arguments
        filepath -- path to the manifest file
    """
    filepath = Path(filepath)
    LOGGER.info("Reading pack-manifest file %s", filepath)
    with filepath.open() as f:
        return load(f)


def load(filelike):
    """
    Read a packmanifest from a filelike object
    """
    pack_manifest = json.load(filelike)
    validate(pack_manifest)
    pack_manifest["pack-version"] = utils.Version(pack_manifest["pack-version"])
    return pack_manifest


def from_str(string):
    pack_manifest = json.loads(string)
    validate(pack_manifest)
    pack_manifest["pack-version"] = utils.Version(pack_manifest["pack-version"])
    return pack_manifest


def check_packmodes(packmodes, packmode_list):
    """
    Check that the packmodes are defined

    Arguments
        packmodes -- packmodes definition of a pack manifest
        packmode_list -- packmode to verify
    
    Raises
        ValueError if some packmodes are undefined
    """
    undefined = set(packmode_list) - (packmodes.keys() | {"server"})
    if undefined:
        raise ValueError("Undefined packmodes %s", undefined)


def write(pack_manifest, filepath: Path):
    """
    Write a pack manifest to a file. Doesn't validate it. Use "make"
    to ensure you create a proper pack manifest

    Arguments
        pack_manifest -- pack_manifest to write
        filepath -- destination file
    """
    with Path(filepath).open("w") as f:
        json.dump(pack_manifest, f, indent=4)


def dump(pack_manifest, fp):
    """
    Write a pack manifest to a file-like object. Doesn't validate it, make() to make a
    proper one.

    Arguments
        pack_manifest -- pack manifest to write
        fp -- file object to write to
    """
    fp.write(json.dumps(pack_manifest, indent=4).encode("utf-8"))


def make(
    pack_version: utils.Version,
    packmodes: Mapping[str, List[str]],
    mods: List[Mapping[str, str]],
    overrides: Mapping[str, str],
    override_cache: Mapping[str, str],
    *,
    current_packmodes: List[str] = None,
):
    """
    Creates and validates a new pack manifest

    Arguments:
        See the json schema MANIFEST_SCHEMA for the schema of a pack manifest
    
    Returns
        A new, validated pack manifest
    
    Raises
        See validate_pack_manifest()
    """
    LOGGER.info("Creating new pack manifest")
    pack_manifest = {"pack-version": str(pack_version), "packmodes": packmodes}
    if current_packmodes:
        pack_manifest["current-packmodes"] = current_packmodes
    pack_manifest.update(
        {"mods": mods, "overrides": overrides, "override-cache": override_cache}
    )
    validate(pack_manifest)
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


def get_all_dependencies(packmodes, packmode_list) -> Set[str]:
    """
    Returns the set of packmodes to include when selecting packmode_list

    Arguments
        packmodes -- packmodes definition of a pack_manifest object
        packmode_list -- list of selected packmodes

    Returns
        set of packmode_list and all their dependencies
    """
    check_packmodes(packmodes, packmode_list)
    packmodes = {"server"}
    stack = list(packmode_list)
    while stack:
        pkm = stack.pop()
        if pkm not in packmodes:
            packmodes.add(pkm)
            for dep in packmodes[pkm]:
                stack.append(dep)
    return packmodes


def get_selected_mods(pack_manifest, packmode_list):
    """
    Returns the list of mods that should be includes given the selected packmodes

    Arguments
        pack_manifest -- pack_manifest object
        packmode_list -- list of selected packmodes
    
    Returns
        The subset of pack_manifest["mods"] that belong to the selected packmodes or
            their dependencies
    """
    LOGGER.info("Selecting mods for packmodes %s", ", ".join(sorted(packmode_list)))
    return [
        mod.copy()
        for mod in pack_manifest["mods"]
        if mod["packmode"]
        in get_all_dependencies(pack_manifest["packmodes"], packmode_list)
    ]


def get_selected_overrides(pack_manifest, packmode_list):
    """
    Returns the list of selected overrides

    Arguments
        pack_manifest -- pack manifest object to select overrides from
        packmode_list -- list of packmodes to include

    Returns
        a subset of pack_manifest["override-cache"] that belong to the provided packmodes
            of their dependencies
    """
    LOGGER.info(
        "Selecting overrides for packmodes %s", ", ".join(sorted(packmode_list))
    )
    get_packmode = lambda path: get_override_packmode(pack_manifest["overrides"], path)
    return {
        filepath: hsh
        for filepath, hsh in pack_manifest["override-cache"].items()
        if get_packmode(filepath)
        in get_all_dependencies(pack_manifest["packmodes"], packmode_list)
    }
