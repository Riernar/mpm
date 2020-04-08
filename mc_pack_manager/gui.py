"""
Part of the Minecraft Pack Manager utility (mpm)

Module for GUIs used in mpm
"""
# Standard lib import
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
import logging
from pathlib import Path, PurePath
import tkinter as tk
import tkinter.ttk as ttk

# Local import
from . import manifest
from . import utils

LOGGER = logging.getLogger("mpm.gui")

ttk.FrameSave = ttk.Frame
ttk.Frame = ttk.LabelFrame


class Dropdown(ttk.Combobox):
    def __init__(self, master, values, *args, interactive=True, **kwargs):
        state = "readonly" if not interactive else None
        width = max(len(str(v)) for v in values) + 1
        values = list(values)
        super().__init__(
            master, *args, state=state, values=values, width=width, **kwargs
        )
        if values:
            self.set(values[0])

    def set_values(self, values):
        selected = self.get()
        values = list(values)
        self.config(values=values)
        self.set(selected if selected in values else values[0])


class MultiSelector(ttk.Treeview):
    """
    Widget to select/deselect multiple element in a list, with a scrollbar
    """

    def __init__(self, master, values, *args, height=5, min_height=3, **kwargs):
        self.frame_ = ttk.Frame(master=master)
        super().__init__(
            *args,
            master=self.frame_,
            show="tree",
            columns=["cache"],
            height=max(3, min(len(values), height)),
            **kwargs
        )
        self.height_arg = height
        self.min_height_arg = min_height
        self.column("cache", width=0, minwidth=0, stretch=False)
        self.bind("<1>", self.on_click)
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
        self.button_frame.pack(side="bottom", fill="x")
        self.button_all.pack(side="left", fill="x", expand=True)
        self.button_clear.pack(side="left", fill="x", expand=True)
        self.button_toggle.pack(side="left", fill="x", expand=True)
        self.scrollbar_ = ttk.Scrollbar(
            master=self.frame_, orient=tk.VERTICAL, command=self.yview
        )
        self.configure(yscrollcommand=self.scrollbar_.set)
        self.scrollbar_.pack(side="right", expand=False, fill="y")
        self.pack(side="left", expand=True, fill="both")
        self.set_values(values)
        self.pack = self.frame_.pack
        self.grid = self.frame_.grid

    def adapt_display(self, item_number):
        height = max(self.min_height_arg, min(item_number, self.height_arg))
        self.config(height=height)

    def set_values(self, values):
        selection = set(self.get_selection())
        self.select_clear()
        self.delete(*self.get_children())
        for value in values:
            self.insert("", "end", text=str(value), values=(value,))
        self.set_selection(selection & set(values))
        self.adapt_display(len(values))

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
    undefined_value = "__UNDEFINED__"

    def __init__(self, master, values, *args, height=13, min_height=7, **kwargs):
        """
        Arguments
            master -- parent widget
            values -- nested structure to select from. Either:
                - a nested dict, with key mapping to all sub-elements and leaves ammped to '{}'
                - an iterable of items, where item an item is the path from the root
                    to the last element
        """
        super().__init__(
            master, values, *args, height=height, min_height=min_height, **kwargs
        )
        self.bind("<Double-Button-1>", self.on_double_click)
        self.click_job = None

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

    def _rec_insert(self, mapping, prefix=tuple(), inserted=None):
        parent = self.sep_char.join(prefix)
        if inserted is None:
            inserted = set()
        for key, value in mapping.items():
            node_id = self.sep_char.join(prefix + (key,))
            if not self.exists(node_id):
                self.insert(
                    parent=parent,
                    index="end",
                    iid=node_id,
                    text=key,
                    values=node_id if not value else self.undefined_value,
                    open=True,
                )
                inserted.add(node_id)
            if value:
                self._rec_insert(value, prefix=prefix + (key,), inserted=inserted)
        return inserted

    def set_values(self, nested_values):
        selection = self.selection()
        children = list(self.get_children())
        if children:
            self.delete(*self.get_children())
        if isinstance(nested_values, Mapping):
            new_ids = self._rec_insert(nested_values)
        else:
            new_ids = self._rec_insert(self._deepen(nested_values))
        common_ids = set(selection) & new_ids
        if common_ids:
            self.selection_add(tuple(common_ids))
        self.adapt_display(len(nested_values))

    def get_selection(self):
        # excludes nodes which are "directory" nodes and where not present leaves in the initial input
        return [
            tuple(self.item(item, "values")[0].split(self.sep_char))
            for item in self.selection()
            if self.item(item, "values")[0] != self.undefined_value
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
        if self.click_job is not None:
            self.after_cancel(self.click_job)
        item = self.identify("item", event.x, event.y)
        if item:
            self.click_job = self.after(200, self.clicked, item)
        return "break"

    def clicked(self, item):
        if item in self.selection():
            self.select_clear(item)
        else:
            self.select_all(item)

    def on_double_click(self, event):
        """
        Open/Close the item
        """
        if self.click_job is not None:
            self.after_cancel(self.click_job)
        item = self.identify("item", event.x, event.y)
        if self.get_children(item):
            self.item(item, open=not self.item(item, "open"))
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
        self.root.title(title)
        self.top = ttk.Frame(self.root)
        self.left = ttk.Frame(self.top)
        self.sep = ttk.Separator(self.top, orient=tk.VERTICAL)
        self.right = ttk.LabelFrame(self.top, text="Current Assignements")
        self.bottom = ttk.Frame(self.root)
        self.status = ttk.Label(
            self.bottom, text="This is the status text ! Message appears here"
        )
        self.finish = ttk.Button(self.bottom, text="Finish", command=self.on_closing)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.top.pack(side="top", expand=True, fill="both")

        self.left.grid(row=0, column=0, sticky="nsew")
        self.sep.grid(row=0, column=1, sticky="ns")
        self.right.grid(row=0, column=2, sticky="nsew")
        self.top.grid_columnconfigure(0, weight=1, uniform="columns")
        self.top.grid_columnconfigure(1, weight=0)
        self.top.grid_columnconfigure(2, weight=1, uniform="columns")
        self.top.grid_rowconfigure(0, weight=1)
        self.bottom.pack(side="bottom", expand=False, fill="x")
        self.status.pack(side="top", expand=True)
        self.finish.pack(side="top", expand=True)

    def on_closing(self, *args, **kwargs):
        try:
            self.on_exit()
        except Exception as err:
            LOGGER.debug("GUI canceled exit due to %s", utils.err_str(err)[:-1])
            LOGGER.debug("Tracebacl:\n%s", utils.err_traceback(err))
            self.status.config(text=utils.err_str(err))
        else:
            self.root.quit()

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
        self.num_rows = 3
        self.packmodes = packmodes
        self.SelectorClass = SelectorClass
        # left area
        ## Assignement
        self.left_top = ttk.LabelFrame(self.left, text="Unassigned elements")
        self.selector_unassigned = SelectorClass(master=self.left_top, values=[])
        self.selector_packmode = Dropdown(
            master=self.left_top,
            values=self.packmodes.keys() | {"server"},
            interactive=False,
        )
        self.button_assign = ttk.Button(
            self.left_top, text="Assign to -->", command=self.on_assign
        )
        self.selector_unassigned.pack(side="left", expand=True, fill="both")
        self.button_assign.pack(side="left", expand=False)
        self.selector_packmode.pack(side="left", expand=False)

        ## Packmode creation
        self.left_bottom = ttk.LabelFrame(self.left, text="Add new packmode")
        self.selector_dependencies = MultiSelector(master=self.left_bottom, values=[])
        self.entry_name = ttk.Entry(self.left_bottom)
        self.button_create = ttk.Button(
            self.left_bottom, text="Add packmode", command=self.on_add
        )
        self.selector_dependencies.pack(side="left", expand=False, fill="y")
        self.entry_name.pack(side="left", expand=False)
        self.button_create.pack(side="left", expand=False)
        ## Packing sub-areas
        self.left_top.pack(side="top", expand=True, fill="both")
        self.left_bottom.pack(side="top", expand=True, fill="both")
        # right area
        self.packmode_uis = {
            packmode: self.make_packmode_ui(self.right, packmode)
            for packmode in (self.packmodes.keys() | {"server"})
        }
        self.button_unassign = ttk.Button(
            self.right, text="Unassign", command=self.on_unassign
        )
        self.button_unassign.grid(row=0, column=0, rowspan=3)
        self.refresh_uis()

    def make_packmode_ui(self, parent, packmode_name):
        ui = {}
        ui["frame"] = ttk.LabelFrame(parent, text=packmode_name)
        ui["selector"] = self.SelectorClass(master=ui["frame"], values=[])
        ui["selector"].pack(side="top", expand=True, fill="both")
        return ui

    def on_add(self):
        name = self.entry_name.get()
        if name in self.packmodes.keys() | {"server"}:
            self.status.config(text="Packmode '%s' already exists !" % name)
            LOGGER.debug("Couldn't create '%s', it already exists", name)
            return
        self.packmodes[name] = self.selector_dependencies.get_selection()
        try:
            manifest.validate_dependencies(self.packmodes)
        except Exception as err:
            msg = "Couldn't create '%s', validation failed due to %s" % (
                name,
                utils.err_str(err),
            )
            self.status.config(text=msg)
            del self.packmodes[name]
            LOGGER.debug(msg)
            return
        self.packmode_uis[name] = self.make_packmode_ui(self.right, name)
        self.entry_name.delete(0, "end")
        LOGGER.debug("Created packmode '%s'", name)
        self.refresh_uis()

    @abstractmethod
    def refresh_uis(self):
        self.selector_packmode.set_values(sorted(self.packmodes.keys() | {"server"}))
        self.selector_dependencies.set_values(
            sorted(self.packmodes.keys() | {"server"})
        )
        for packmode, ui in self.packmode_uis.items():
            ui["frame"].grid_forget()
        for i, (packmode, ui) in enumerate(sorted(self.packmode_uis.items())):
            ui["frame"].grid(
                row=i % self.num_rows, column=1 + (i // self.num_rows), sticky="nsew"
            )
            self.right.grid_columnconfigure(
                1 + (i // self.num_rows), weight=1, uniform="assignement_columns"
            )
            self.right.grid_rowconfigure(i % self.num_rows, weight=1)

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
        self.mod_list = mods
        super().__init__(
            SelectorClass=MultiSelector, title="Mod assignement UI", packmodes=packmodes
        )

    def refresh_uis(self):
        super().refresh_uis()
        self.selector_unassigned.set_values(
            sorted([mod["name"] for mod in self.mod_list if "packmode" not in mod])
        )
        for packmode, ui in self.packmode_uis.items():
            ui["selector"].set_values(
                sorted(
                    [
                        mod["name"]
                        for mod in self.mod_list
                        if mod.get("packmode") == packmode
                    ]
                )
            )

    def on_assign(self):
        packmode = self.selector_packmode.get()
        selection = self.selector_unassigned.get_selection()
        for mod in self.mod_list:
            if mod["name"] in selection:
                mod["packmode"] = packmode
        LOGGER.debug(
            "Assigned the following mods to %s:\n - %s",
            packmode,
            "\n - ".join(sorted(selection)),
        )
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
        LOGGER.debug(
            "Unassigned the following mods:\n - %s", "\n - ".join(sorted(selection))
        )
        self.refresh_uis()

    def on_exit(self):
        if any("packmode" not in mod for mod in self.mod_list):
            raise ValueError("Some mods don't have a packmode")


class OverridesGUI(PackmodeBaseGUI):
    """
    GUI for assigning overrides to packmodes
    """

    def __init__(self, packmodes, override_cache, overrides):
        self.overrides = overrides
        self.override_packmode_map = {
            PurePath(filepath).parts: manifest.get_override_packmode(
                overrides, filepath
            )
            for filepath in sorted(override_cache.keys())
        }
        super().__init__(
            SelectorClass=NestedMultiSelector,
            title="Overrides assignment UI",
            packmodes=packmodes,
        )

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
        root = {"packmode": None, "weight": None, "children": {}}
        for filepath, packmode in self.override_packmode_map.items():
            node = root
            for part in filepath:
                node = node["children"].setdefault(
                    part, {"packmode": None, "weight": None, "children": {}}
                )
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
            if isinstance(node, tuple) and node[0]["packmode"] is None:
                # all children have been seen already, assing packmode
                node = node[0]  # unpack the actual node
                weights = defaultdict(int)
                for child in node["children"].values():
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

    def _write_overrides(
        self, node, parent=None, parent_packmode=None, path_parts=tuple(), root=None
    ):
        """
        Uses recursive DFS to write the overrides from a weigthed, assigned file tree
        """
        if root is None:
            root = node
        if (parent is root) or (
            parent_packmode and node["packmode"] != parent_packmode
        ):
            self.overrides[str(PurePath(*path_parts))] = node["packmode"]
        for key, child in node["children"].items():
            self._write_overrides(
                node=child,
                parent=node,
                parent_packmode=node["packmode"],
                path_parts=path_parts + (key,),
                root=root,
            )

    def on_exit(self):
        if any(v is None for v in self.override_packmode_map.values()):
            raise ValueError("Some overrides don't have a packmode")
        self.status.config(text="Compacting overrides assignemnts ...")
        LOGGER.info("Compacting overrides assignemnts")
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
    LOGGER.info("Creating GUI for mods assignements")
    gui = ModGUI(deepcopy(packmodes), deepcopy(mods))
    gui.run()
    return gui.packmodes, gui.mod_list


def assign_overrides(packmodes, overrides, override_cache):
    """
    Assign overrides to packmodes using a GUI, and compact
    assignment

    Arguments
        packmodes -- "packmodes" property of a pack_manifest, the packmodes definitions
        overrides -- "overrides" property of a pack_manifest, overrides assignemnts to packmodes
        override_cache -- "overrides-cache" property of a pack_manifest, list of overrides filepath and hash
    
    Returns
        (packmodes, overrides)
        packmodes definition (some packmodes may be added in the GUI)
        overrides assignements to packmodes
    """
    LOGGER.info("Creating GUI for overrides assignements")
    gui = OverridesGUI(deepcopy(packmodes), override_cache, deepcopy(overrides))
    gui.run()
    return gui.packmodes, gui.overrides
