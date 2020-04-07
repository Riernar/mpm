"""
Part of the Minecraft Pack Manager utility (mpm)

Miscellaneous utilities
"""
# Standard lib import
from collections import namedtuple
from collections.abc import Iterable
from functools import wraps
import hashlib
import inspect
import logging
from pathlib import Path
from traceback import format_exception_only
from typing import TypeVar, Mapping, Iterable, Union, List

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")

Node = namedtuple("Node", ["value"])


class Version:
    """
    Represents dot separated version numbers
    """

    def __init__(self, *args):
        """
        Create a new version object

        Arguments can be:
            - a single string, as in  Version("1.1.1")
            - an single iterable, as in Version([1,1,1])
            - any number of int()-compatible args, as in Version(1,'1',1)
        """
        if len(args) == 1 and isinstance(args[0], str):
            self._data = tuple(int(i) for i in str(args[0]).split("."))
        elif len(args) == 1 and isinstance(args[0], Iterable):
            self._data = tuple(int(i) for i in args[0])
        else:
            self._data = tuple(int(i) for i in args)

    def __str__(self):
        return ".".join(str(i) for i in self._data)

    def __repr__(self):
        return "%s%s('%s')" % (
            f"{str(self.__module__)}." if self.__module__ else "",
            str(self.__class__.__name__),
            str(self),
        )

    def __lt__(self, other):
        if isinstance(other, Version):
            return self._data < other._data
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, Version):
            return self._data <= other._data
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, Version):
            return self._data == other._data
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Version):
            return self._data >= other._data
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, Version):
            return self._data > other._data
        return NotImplemented

    def incr(self):
        return Version(self._data[:-1] + (self._data[-1] + 1,))


class AutoFormatError(Exception):
    """
    Mixin class that makes error automatically format the 'message'
        (if any) parameter of __init__ argument with str.format(), passing
        the dictionary of over parameters
    """

    @staticmethod
    def _init_wrapper(init_method):
        init_sig = inspect.signature(init_method)

        @wraps(init_method)
        def wrapped_init(*args, **kwargs):
            bound_args = init_sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            if "message" in bound_args.arguments:
                msg = bound_args.arguments.pop("message")
                bound_args.arguments["message"] = msg.format(**bound_args.arguments)
            return init_method(*bound_args.args, **bound_args.kwargs)

        return wrapped_init

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__init__ = AutoFormatError._init_wrapper(cls.__init__)


class DFSError(Exception):
    """
    Error while preforming DFS
    """


class RuntimeDFSError(AutoFormatError, DFSError):
    """
    Class for runtime problems in DFS (should not happen)
    """

    def __init__(self, stack, path, message="Stack: {stack}, Path:{path}"):
        super().__init__(message)
        self.stack = stack
        self.path = path


class CycleDFSError(AutoFormatError, DFSError):
    """
    Exception when a cycle is encountered in a DFS

    Atributes
        cycle -- cycle found, as a list of nodes
        message -- explanation of the error (autoformated, see AutoFormatError base class)
    """

    def __init__(self, cycle, message="Found cycle while performings dfs: {cycle}"):
        # message is auto-formated by "AutoFormatError mixin"
        super().__init__(message)
        self.cycle = cycle
        self.message = message


def dfs(
    graph: Mapping[T, Iterable[T]], u: T, v: T = None, raise_cycle: bool = False
) -> Union[None, List[T]]:
    """
    Searches a path in a graph g between node u and v, using depth-first search

    Argument
        graph -- directed graph to search in, represented as adjacency list
        u -- starting node
        v -- end node. If None, searches cycles in the DFS traversal tree starting from u
        raise_cycle -- raise an exception is a cycle is found during path search
    
    Returns
        A path between u and v, or None if u and v are not connected
        OR None if v is None and there is no cycle found starting from u
    
    Raises
        RuntimeDFSError -- if there was an error while running the algorithm
        CycleDFSError --  if raise_cycle is True and a cycle was found
    """
    if v is None:
        raise_cycle = True
    if not raise_cycle and (u not in graph or v not in graph):
        return None
    is_active = {}
    path = []
    stack = [u]
    while stack:
        node = stack.pop()
        if isinstance(node, Node):
            is_active[node.value] = False
            if path[-1] != node.value:
                raise RuntimeError(stack=stack + [node], path=path)
            path.pop()
            continue
        path.append(node)
        if node == v:
            return path
        is_active[node] = True
        stack.append(Node(node))
        for child in graph.get(node, []):
            if is_active.get(child) is None:
                stack.append(child)
            elif not is_active[child]:
                continue
            else:
                cycle = [node]
                while stack and (len(cycle) < 2 or cycle[-1] != node):
                    prev = stack.pop()
                    if not isinstance(prev, Node):
                        continue
                    if cycle[-1] in graph.get(prev.value, []):
                        cycle.append(prev.value)
                raise CycleDFSError(cycle=cycle[::-1])


def file_hash(filepath: Path):
    """
    Compute a hash of the file content
    Thanks to https://stackoverflow.com/questions/22058048/hashing-a-file-in-python

    Arguments
        filepath -- path to the file to hash
    
    Returns
        a hash of the file
    """
    hsh = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with Path(filepath).open("rb", buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            hsh.update(mv[:n])
    return hsh.hexdigest()


def err_str(err):
    """
    Utility function to get a nice str of an Exception for display purposes
    """
    return "\n".join(format_exception_only(type(err), err))
