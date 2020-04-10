"""
Widgets built on top of tkinter

Part of the Minecraft Pack Manager utility (mpm)
"""
from collections.abc import Mapping
import tkinter as tk
import tkinter.ttk as ttk


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
        self.configure(values=values, width=max(len(str(v)) for v in values) + 1)
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
            columns=[],
            height=max(3, min(len(values), height)),
            **kwargs
        )
        self.height_arg = height
        self.min_height_arg = min_height
        # self.column("cache", width=0, minwidth=0, stretch=False)
        self.bind("<1>", self.on_click)
        # Under buttons
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
        self.id_value_map = {}
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
        self.id_value_map = {
            self.insert("", "end", text=str(value)): value for value in values
        }
        self.set_selection(selection & set(values))
        self.adapt_display(len(values))

    def get_selection(self):
        """
        Returns the selected element from the `values` passed to `__init__()`
        """
        return [
            self.id_value_map[item]
            for item in self.selection()
            if item in self.id_value_map
        ]

    def set_selection(self, values):
        """
        Set the current selection from a subset of 'values' passed to __init__
        """
        self.selection_set(
            [item for item in self.get_children() if self.id_value_map[item] in values]
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
    Widget for multiselection with nested structures, such as a file hierarchy
    """

    sep_char = "/"
    undefined_value = "__UNDEFINED__"

    def __init__(self, master, values, *args, height=13, min_height=7, **kwargs):
        """
        Arguments
            master -- parent widget
            values -- nested structure to select from. Either:
                - a nested dict, with key mapping to all sub-elements and leaves ammped to '{}'
                - an iterable of tuples, where an inner iterable represents a path from root to element
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

    def _rec_insert(self, mapping, prefix=tuple(), parent=""):
        for key, value in mapping.items():
            item = self.insert(parent=parent, index="end", text=str(key), open=True,)
            if value:
                self._rec_insert(value, prefix=prefix + (key,), parent=item)
            else:
                self.id_value_map[item] = prefix + (key,)

    def set_values(self, nested_values):
        selection = self.get_selection()
        if self.get_children():
            self.delete(*self.get_children())
        self.id_value_map = {}
        if isinstance(nested_values, Mapping):
            self._rec_insert(nested_values)
        else:
            self._rec_insert(self._deepen(nested_values))
        self.selection_add(
            [item for item, value in self.id_value_map.items() if value in selection]
        )
        self.adapt_display(len(nested_values))

    def get_selection(self):
        # excludes nodes which are "directory" nodes and where not present leaves in the initial input
        return [
            self.id_value_map[item]
            for item in self.selection()
            if item in self.id_value_map
        ]

    def set_selection(self, nested_values):
        if isinstance(nested_values, Mapping):
            nested_values = self._flatten_dfs(nested_values)
        self.selection_set(
            [
                item
                for item, value in self.id_value_map.items()
                if value in nested_values
            ]
        )

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
