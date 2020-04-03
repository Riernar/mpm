import tkinter as tk
import tkinter.ttk as ttk

from . import pymanifest
from . import utils


class Dropdown(ttk.Combobox):
    def __init__(self, master, values, *args, interactive=True, **kwargs):
        state = "readonly" if not interactive else None
        width = max(len(str(v)) for v in values) + 1
        super().__init__(
            master, *args, state=state, values=values, width=width, **kwargs
        )
        self.set(values[0])

    def set_values(self, values):
        self.config(values=values)


class MultiSelector(ttk.Treeview):
    """
    Widget to select/deselect multiple element in a list, with a scrollbar
    """

    def __init__(self, master, values, *args, height=5, **kwargs):
        self.frame_ = ttk.Frame(master=master)
        super().__init__(
            *args,
            master=self.frame_,
            show="",
            columns=["value"],
            height=min(len(values), height),
            **kwargs
        )
        self.bind("<1>", self.on_click)
        self.set_values(values)
        # self.column("#1", minwidth=8 * max(len(v) for v in values))
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

    def get_selection(self):
        """
        Returns the selected element from the `values` passed to `__init__()`
        """
        return [self.item(item)["values"][0] for item in self.selection()]

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

    def set_values(self, values):
        self.select_clear()
        self.delete(*self.get_children())
        for value in values:
            self.insert("", "end", values=(value,))


class BaseGUI:
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
            self.validate_result()
        except Exception as err:
            self.status.config(text=utils.err_str(err))
        else:
            self.root.destroy()

    def validate_result(self):
        pass


class ModGUI(BaseGUI):
    """
    GUI for assigning mods to packmodes
    """

    def __init__(self, packmodes, mods):
        super().__init__(self, "Mod assignement UI")
        self.mod_list = mods
        self.packmodes = packmodes
        # left area
        ## Assignement
        self.left_top = ttk.Frame(self.left)
        self.selector_unassigned = MultiSelector(self.left_top, [])
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

    def make_packmode_ui(self, parent, packmode):
        ui = {}
        ui["frame"] = ttk.LabelFrame(parent, title=packmode)
        ui["selector"] = MultiSelector(ui["frame"], [])
        return ui

    def refresh_uis(self):
        self.selector_unassigned.set_values(
            [mod["name"] for mod in self.mod_list if "packmode" not in mod]
        )
        packmode_sel = self.selector_packmode.get()
        self.selector_packmode.set_values(self.packmodes.keys() | {"server"})
        self.selector_packmode.set(packmode_sel)
        for packmode, ui in self.packmode_uis.items():
            ui["selector"].set_value(
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

    def validate_result(self):
        if any("packmode" not in mod for mod in self.mod_list):
            raise ValueError("Some mods don't have a packmode")

    def run(self):
        self.root.mainloop()
        self.root.destroy()


class OverridesGUI(BaseGUI):
    """
    GUI for assigning overrides to packmodes
    """

    def __init__(self, toverrides_cache, overrides):
        super().__init__("Overrides assignment UI")
        # TODO


def assign_mods(packmodes_defs, mods):
    """
    Assign mods to packmodes using a GUI, modifying 'mods' in-place

    Arguments
        packmodes_defs -- packmode definitions, the "packmodes" property
            of a pack_manifest
        mods -- mods definitions, the "mods" property of a pack manifest
            ! their names must be resolved !
    
    Return
        ('packmodes_defs', 'mods'), modified in-place
    """
    unassigned = [mod for mod in mods if "packmode" not in mod]
    if not unassigned:
        return packmodes_defs, mods
    gui = ModGUI(packmodes_defs, mods)
    gui.run()
    return gui.packmodes, gui.mod_list
