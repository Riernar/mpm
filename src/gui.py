import tkinter as tk
import tkinter.ttk as ttk
from collections import defaultdict
from collections.abc import Mapping
from abc import ABC, abstractmethod
from pathlib import Path, PurePath

from . import pymanifest
from . import utils


class Dropdown(ttk.Combobox):
    def __init__(self, master, values, *args, interactive=True, **kwargs):
        state = "readonly" if not interactive else None
        width = max(len(str(v)) for v in values) + 1
        super().__init__(
            master, *args, state=state, values=values, width=width, **kwargs
        )
        if values:
            self.set(values[0])

    def set_values(self, values):
        selected = self.get()
        self.config(values=values)
        self.set(selected if selected in values else values[0])


class MultiSelector(ttk.Treeview):
    """
    Widget to select/deselect multiple element in a list, with a scrollbar
    """

    def __init__(self, master, values, *args, height=5, **kwargs):
        self.frame_ = ttk.Frame(master=master)
        super().__init__(
            *args,
            master=self.frame_,
            show="tree",
            columns=["cache"],
            height=min(len(values), height),
            **kwargs
        )
        self.column("cache", width=0, minwidth=0, stretch=False)
        self.bind("<1>", self.on_click)
        self.set_values(values)
        self.button_frame = ttk.Frame(master=self.frame_)
        self.button_all = ttk.Button(
            master=self.button_frame, text="All", command=self.select_all
        )
        self.button_clear = ttk.Button(
            master=self.button_frame, text="Clear", command=self.select_clear
        )
        self.button_toggle = ttk.Button(
            master=self.button_frame, text="Toggle", command=self.select_toggle
        )
        self.button_frame.pack(side="bottom")
        self.button_all.pack(side="left")
        self.button_clear.pack(side="left")
        self.button_toggle.pack(side="left")
        if height < len(values):
            self.scrollbar_ = ttk.Scrollbar(
                master=self.frame_, orient=tk.VERTICAL, command=self.yview
            )
            self.configure(yscrollcommand=self.scrollbar_.set)
            self.scrollbar_.pack(side="right", expand=True, fill="y")
        self.pack(side="left", expand=True, fill="both")
        self.pack = self.frame_.pack
        self.grid = self.frame_.grid

    def set_values(self, values):
        selection = set(self.get_selection())
        self.select_clear()
        self.delete(*self.get_children())
        for value in values:
            self.insert("", "end", text=str(value), values=(value,))
        self.set_selection(selection & set(values))

    def get_selection(self):
        """
        Returns the selected element from the `values` passed to `__init__()`
        """
        return [self.item(item, "values")[0] for item in self.selection()]

    def set_selection(self, values):
        """
        Set the current selection from a subset of 'values' passed to __init__
        """
        self.selection_set(
            [
                item
                for item in self.get_children()
                if self.item(item, "values")[0] in values
            ]
        )

    def on_click(self, event):
        """
        Toggle the selection of an item that is clicked on instead of
        the default behavior that is to select only that item
        """
        item = self.identify("item", event.x, event.y)
        if item:
            if item in self.selection():
                self.selection_remove(item)
            else:
                self.selection_add(item)
            return "break"

    def select_all(self):
        """
        Select all items
        """
        self.selection_add(*self.get_children())

    def select_clear(self):
        """
        Deselect all items
        """
        self.selection_remove(*self.get_children())

    def select_toggle(self):
        """
        Toggle the selection of all items
        """
        self.selection_toggle(*self.get_children())


class NestedMultiSelector(MultiSelector):
    """
    Widget for multiselection with nested structures, such a file hierarchy
    """

    sep_char = "/"

    def __init__(self, master, nested_values, *args, height=10, **kwargs):
        """
        Arguments
            master -- parent widget
            nested_values -- nested structure to select from. Either:
                - a nested dict, with key mapping to all sub-elements and leaves ammped to '{}'
                - an iterable of items, where item an item is the path from the root
                    to the last element
        """
        super().__init__(master, nested_values, *args, height=height, **kwargs)

    def _flatten_dfs(self, mapping, prefix=tuple(), flattened=None):
        flat_values = flattened or []
        for key, value in mapping.items():
            if value:
                self._flatten_dfs(
                    mapping=value, prefix=prefix + (key,), flattened=flat_values
                )
            else:
                flat_values.append(prefix + (key,))
        return flat_values

    def _deepen(self, flat_data):
        nested_mapping = {}
        for element in flat_data:
            node = nested_mapping
            for value in element:
                node = node.setdefault(value, {})
        return nested_mapping

    def _rec_insert(self, mapping, prefix=tuple()):
        parent = self.sep_char.join(prefix)
        for key, value in mapping.items():
            node_id = self.sep_char.join(prefix + (key,))
            if not value:
                # This is a leaf element, it was in the initial hierarchy
                data = prefix + (key,)
            else:
                # This is not a leaf element, it was not in the initial hierarchy
                # it shoudl *not* be returned by the "get_selection" method
                data = None
            if not self.exists(node_id):
                self.insert(
                    parent=parent,
                    index="end",
                    iid=node_id,
                    text=key,
                    values=[data],
                    open=False,
                )
            if value:
                self._rec_insert(value, prefix=prefix + (key,))

    def set_values(self, nested_values):
        selection = self.selection()
        self.delete(self.get_children())
        if isinstance(nested_values, Mapping):
            self._rec_insert(nested_values)
        else:
            self._rec_insert(self._deepen(nested_values))
        self.selection_add(selection)

    def get_selection(self):
        # excludes nodes which are "directory" nodes and where not present leaves in the initial input
        return [
            self.item(item, "values")[0]
            for item in self.selection()
            if self.item(item, "values")[0] is not None
        ]

    def set_selection(self, nested_values):
        if isinstance(nested_values, Mapping):
            nested_values = self._flatten_dfs(nested_values)
        self.selection_set([self.sep_char.join(element) for element in nested_values])

    def on_click(self, event):
        """
        Toggle the selection of an item that is clicked on instead of
        the default behavior that is to select only that item
        If the items is selected/deselected, all its childrens enter the same
            selection state
        """
        item = self.identify("item", event.x, event.y)
        if item:
            if item in self.selection():
                self.select_clear(item)
            else:
                self.select_all(item)
            return "break"

    def select_all(self, item=""):
        self.selection_add(item)
        for child in self.get_children(item):
            self.select_all(child)

    def select_clear(self, item=""):
        self.selection_remove(item)
        for child in self.get_children(item):
            self.select_clear(child)

    def select_toggle(self, item=""):
        self.selection_toggle(item)
        for child in self.get_children(item):
            self.select_toggle(child)


class BaseGUI(ABC):
    """
    Base GUI for packmode assignment
    """

    def __init__(self, title):
        self.root = tk.Tk()
        self.root.set_title(title)
        self.left = ttk.Frame(self.root)
        self.sep = ttk.Separator(self.root)
        self.right = ttk.Frame(self.root)
        self.bottom = ttk.Frame(self.root)
        self.status = ttk.Label(self.bottom)
        self.finish = ttk.Button(self.bottom, text="Finish", command=self.on_closing)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.left.pack(side="left", expand=True, fill="both")
        self.sep.pack(side="left", exapnd=True, fill="y")
        self.right.pack(side="left", expand=True, fill="both")
        self.status.pack(side="top", expand=True)
        self.finish.pack(side="top", expand=True)
        self.bottom.pack(side="bottom", expand=True, fill="x")

    def on_closing(self, *args, **kwargs):
        try:
            self.on_exit()
        except Exception as err:
            self.status.config(text=utils.err_str(err))
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()
        self.root.destroy()

    @abstractmethod
    def on_exit(self):
        pass


class PackmodeBaseGUI(BaseGUI, ABC):
    """
    Base GUI to assign packmodes
    """

    def __init__(self, SelectorClass, title, packmodes):
        super().__init__(title)
        self.packmodes = packmodes
        self.SelectorClass = SelectorClass
        # left area
        ## Assignement
        self.left_top = ttk.Frame(self.left)
        self.selector_unassigned = SelectorClass(self.left_top, [])
        self.selector_packmode = Dropdown(
            self.left_top, self.packmodes.keys() | {"server"}, False
        )
        self.button_assign = ttk.Button(
            self.left_top, text="Assign to -->", command=self.on_assign
        )
        self.button_assign.pack(side="left", expand="True")
        self.selector_packmode.pack(side="left", expand="True")
        self.selector_unassigned.pack(side="top", expand=True, fill="both")
        ## Packmode creation
        self.left_bottom = ttk.Frame(self.left)
        self.selector_dependencies = MultiSelector(self.left_bottom, [])
        self.entry_name = ttk.Entry(self.left_bottom)
        self.button_create = ttk.Button(
            self.left_bottom, text="Add packmode", command=self.on_add
        )
        self.selector_dependencies.pack(side="left", expand=True)
        self.entry_name.pack(side="left", expand=True)
        self.button_create.pack(side="left", expand=True)
        ## Packing sub-areas
        self.left_top.pack(side="top", expand=True, fill="both")
        self.left_bottom.pack(side="top", expand=True, fill="both")
        # right area
        self.packmode_uis = {
            packmode: self.make_packmode_ui(self.right, packmode)
            for packmode in self.packmodes.keys() | {"server"}
        }
        self.button_unassign = ttk.Button(
            self.left, text="Unassign", command=self.on_unassign
        )
        for ui in self.packmode_uis.values():
            ui["frame"].pack(side="top")
        self.button_unassign.pack(side="left")
        self.refresh_uis()

    def make_packmode_ui(self, parent, packmode_name):
        ui = {}
        ui["frame"] = ttk.LabelFrame(parent, title=packmode_name)
        ui["selector"] = self.SelectorClass(ui["frame"], [])
        return ui

    def on_add(self):
        name = self.entry_name.get()
        if name in self.packmodes.keys() | {"server"}:
            self.status.config(text="Packmode '%s' already exists !" % name)
            return
        self.packmodes[name] = self.selector_dependencies.get_selection()
        try:
            pymanifest.validate_dependencies(self.packmodes)
        except Exception as err:
            self.status.config(text=utils.err_str(err))
            del self.packmodes[name]
            return
        new_ui = self.make_packmode_ui(self.right, name)
        new_ui["frame"].pack(side="top")
        self.packmode_uis[name] = new_ui

    @abstractmethod
    def refresh_uis(self):
        self.selector_packmode.set_values(self.packmodes.keys() | {"server"})
        self.selector_dependencies.set_values(self.packmodes.keys() | {"server"})

    @abstractmethod
    def on_assign(self):
        """
        Event handler for when the "assign" button is clicked
        """

    @abstractmethod
    def on_unassign(self):
        """
        Event handler for when the "unassign" button is clicked
        """


class ModGUI(PackmodeBaseGUI):
    """
    GUI for assigning mods to packmodes
    """

    def __init__(self, packmodes, mods):
        super().__init__(
            SelectorClass=MultiSelector, title="Mod assignement UI", packmodes=packmodes
        )
        self.mod_list = mods

    def refresh_uis(self):
        super().refresh_uis()
        self.selector_unassigned.set_values(
            [mod["name"] for mod in self.mod_list if "packmode" not in mod]
        )
        for packmode, ui in self.packmode_uis.items():
            ui["selector"].set_values(
                [
                    mod["name"]
                    for mod in self.mod_list
                    if mod.get("packmode") == packmode
                ]
            )

    def on_assign(self):
        packmode = self.selector_packmode.get()
        selection = self.selector_unassigned.get_selection()
        for mod in self.mod_list:
            if mod["name"] in selection:
                mod["packmode"] = packmode
        self.refresh_uis()

    def on_unassign(self):
        selection = [
            element
            for ui in self.packmode_uis.values()
            for element in ui["selector"].get_selection()
        ]
        for mod in self.mod_list:
            if mod["name"] in selection and "packmode" in mod:
                del mod["packmode"]
        self.refresh_uis()

    def on_exit(self):
        if any("packmode" not in mod for mod in self.mod_list):
            raise ValueError("Some mods don't have a packmode")


class OverridesGUI(PackmodeBaseGUI):
    """
    GUI for assigning overrides to packmodes
    """

    def __init__(self, packmodes, overrides_cache, overrides):
        super().__init__(
            SelectorClass=NestedMultiSelector,
            title="Overrides assignment UI",
            packmodes=packmodes,
        )
        self.overrides = overrides
        self.override_packmode_map = {
            PurePath(entry["filepath"]).parts: pymanifest.get_override_packmode(
                overrides, entry["filepath"]
            )
            for entry in sorted(overrides_cache, key=lambda override: override["filepath"])
        }

    def refresh_uis(self):
        super().refresh_uis()
        self.selector_unassigned.set_values(
            [
                filepath
                for filepath, packmode in self.override_packmode_map.items()
                if packmode is None
            ]
        )
        for key, ui in self.packmode_uis.items():
            ui["selector"].set_values(
                [
                    filepath
                    for filepath, packmode in self.override_packmode_map.items()
                    if packmode == key
                ]
            )

    def on_assign(self):
        packmode = self.selector_packmode.get()
        for parts in self.selector_unassigned.get_selection():
            self.override_packmode_map[parts] = packmode
        self.refresh_uis()

    def on_unassign(self):
        for ui in self.packmode_uis.values():
            for parts in ui["selector"].get_selection():
                self.override_packmode_map[parts] = None
        self.refresh_uis()

    def _build_file_tree(self):
        """
        Builds the file tree for overrides compaction
        """
        # Build file tree with packmode and weigth info (# of file in the packmode)
        root = {
            "packmode": None,
            "weight": None,
            "children": {}
        }
        for filepath, packmode in self.override_packmode_map.items():
            node = root
            for part in filepath:
                node = node["children"].setdefault(part, {"packmode": None, "weight": None, "children": {}})
            node["weight"] = 1
            node["packmode"] = packmode
        return root
    
    def _dfs_assign(self, filetree):
        """
        Uses DFS to assign to directory the packmode with maximum weight

        The override format support assigning a whole directory to a packmode,
        and having exception in that directory
        This method assign the packmode with the most files to the directory,
        so that the least amount of files/directory needs to be specified in
        the "overrides" property
        """
        stack = [filetree]
        while stack:
            node = stack.pop()
            if isinstance(node, tuple) and node["packmode"] is None:
                # all children have been seen already, assing packmode
                node = node[0]  #unpack the actual node
                weights = defaultdict(int)
                for child in node["children"]:
                    weights[child["packmode"]] += child["weight"]
                packmode, weight = max(weights.items(), key=lambda x: x[1])
                node["weight"] = weight
                node["packmode"] = packmode
            elif node["children"]:
                # schedule that node for computation
                stack.append((node,))
                # visit all children first
                for child in node["children"].values():
                    stack.append(child)
    
    def _write_overrides(self, node, parent_packmode=None, path_parts=tuple()):
        """
        Uses recursive DFS to write the overrides from a weigthed, assigned file tree
        """
        if parent_packmode and node["packmode"] != parent_packmode:
            self.overrides[str(PurePath(*path_parts))] = node["packmode"]
        for key, child in node["children"].items():
            self._write_overrides(child, parent_packmode=node["packmode"], path_parts=path_parts + (key,))

    def on_exit(self):
        if any(self.override_packmode_map.values() is None):
            raise ValueError("Some overrides don't have a packmode")
        self.status.config(text="Compacting overrides assignemnts ...")
        # Build the file tree
        root = self._build_file_tree()
        # Assign packmode to directory to compact overrides assignements
        self._dfs_assign(root)
        # Write the overrides, delegating some overrides assignemnt to parent dir
        self.overrides = {}
        self._write_overrides(root)


def assign_mods(packmodes, mods):
    """
    Assign mods to packmodes using a GUI. Might modify args in-place

    Arguments
        packmodes -- packmode definitions, the "packmodes" property
            of a pack_manifest
        mods -- mods definitions, the "mods" property of a pack manifest
            ! their names must be resolved !
    
    Return
        the new ('packmodes', 'mods')
    """
    gui = ModGUI(packmodes, mods)
    gui.run()
    return  gui.packmodes, gui.mod_list

def assign_overrides(packmodes, overrides, overrides_cache):
    """
    Assign overrides to packmodes using a GUI, and compact
    assignment

    Arguments
        packmodes -- "packmodes" property of a pack_manifest, the packmodes definitions
        overrides -- "overrides" property of a pack_manifest, overrides assignemnts to packmodes
        overrides-cache -- "overrides-cache" property of a pack_manifest, list of overrides filepath and hash
    
    Returns
        (packmodes, overrides)
        packmodes definition (some packmodes may be added in the GUI)
        overrides assignements to packmodes
    """
    gui = OverridesGUI(packmodes, overrides_cache, overrides)
    gui.run()
    return gui.packmodes, gui.overrides
