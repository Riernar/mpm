"""
User Interface implementation for packmodes assignement

Part of the Minecraft Pack Manager utility (mpm)
"""
# Standard lib import
from abc import ABC, abstractmethod
from collections import defaultdict
import logging
from pathlib import PurePath
import tkinter as tk
import tkinter.ttk as ttk

# Local import
from .. import manifest
from .. import utils
from ..ui.widgets import Dropdown, MultiSelector, NestedMultiSelector

LOGGER = logging.getLogger("mpm.ui.impl")


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
        ui["frame"] = ttk.LabelFrame(
            parent,
            text=packmode_name
            + (
                "(depends on: %s)" % (", ".join(self.packmodes[packmode_name]))
                if self.packmodes[packmode_name]
                else ""
            ),
        )
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
            manifest.pack.validate_dependencies(self.packmodes)
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
        self.selector_dependencies.select_clear()
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
            ui["frame"].config(
                text=packmode
                + (
                    "(depends on: %s)" % (", ".join(self.packmodes[packmode]))
                    if self.packmodes[packmode]
                    else ""
                )
            )
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

    def __init__(self, packmodes, override_cache, overrides, added=None):
        self.overrides = overrides
        self.override_packmode_map = {
            PurePath(filepath).parts: manifest.pack.get_override_packmode(
                overrides, filepath
            )
            if not added or (filepath not in added)
            else None
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
                pathparts
                for pathparts, packmode in self.override_packmode_map.items()
                if packmode is None
            ]
        )
        for key, ui in self.packmode_uis.items():
            ui["selector"].set_values(
                [
                    pathparts
                    for pathparts, packmode in self.override_packmode_map.items()
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
