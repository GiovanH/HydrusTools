from collections import OrderedDict
import dataclasses
from functools import partial
import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import ClassVar

from .gui_util import Increment, tkwrap
from .multicolumnlistbox import MultiColumnListbox, TreeListItemDict, TreeviewSchema
from .toolwindow import ToolWindow
from ..settings import Settings
from .gui_util import TextCopyWindow



@dataclass
class RelationshipAction():
    target_tag: str
    new_tag: str
    note: str

class RelationshipActionSchema(TreeviewSchema[RelationshipAction]):
    headers: ClassVar[OrderedDict[str, str | None]] = OrderedDict([
        ('target_tag', 'Source Tag'),
        ('new_tag', 'New Relationship'),
        ('note', 'Note'),
    ])

    @staticmethod
    def to_tree_item(item: RelationshipAction) -> TreeListItemDict:
        return {
            "values": [*dataclasses.astuple(item)]
        }


class RelationshipAdderFrame(ttk.Frame):
    def __init__(self, master: ToolWindow, pack_buttons=True, *args_, **kwargs) -> None:
        super().__init__(master, *args_, **kwargs)
        self.toolmaster: ToolWindow = master
        self.logger: logging.Logger = master.logger

        self.initwidget(pack_buttons=pack_buttons)

    def delete_all(self):
        self.tree_tags.delete_all()

    def add_item(self, si: RelationshipAction):
        self.tree_tags.insert_item(RelationshipActionSchema.to_tree_item(si))

    def setSuggestions(self, suggestions: list[RelationshipAction]):
        self.delete_all()
        for si in sorted(suggestions, key=lambda si: si.target_tag):
            self.add_item(si)

    def initwidget(self, pack_buttons: bool) -> None:
        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        counter_main_row.inc()
        self.tree_tags = MultiColumnListbox(self, schema=RelationshipActionSchema)

        with tkwrap(self.tree_tags) as tree:
            # assert isinstance(tree, ttk.Treeview)
            tree.grid(column=0, row=counter_main_row.value, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

        self.btn_selected: partial[ttk.Button] = partial(ttk.Button, text="Copy Import for selected", command=self.copyImport, width=40)
        self.btn_all: partial[ttk.Button] = partial(ttk.Button, text="Copy Import for all", command=self.copyImportAll, width=40)

        if pack_buttons:
            with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as frame_btns:
                frame_btns.grid(row=counter_main_row.inc(), column=0, columnspan=2, sticky="ew")

                ttk.Label(frame_btns, textvariable=self.toolmaster.textvar_status).grid(column=0, row=0, sticky="nsew")

                frame_btns.columnconfigure(0, weight=1)

                btn = self.btn_selected(frame_btns)
                btn.grid(column=1, row=0, sticky="nse")

                btn = self.btn_all(frame_btns)
                btn.grid(column=2, row=0, sticky="nse")

        # self.master.bind("<Delete>", self.deleteSelected)

    def copyImportAll(self, event=None):
        selection: list[tuple[str, str]] = [
            (d['target_tag'], d['new_tag'])
            for d in self.tree_tags.getAllDicts()
        ]

        if len(selection) == 0:
            return

        clip_import = '\n'.join(
            f"{source}\n{ideal}"
            for (source, ideal) in selection
        )
        TextCopyWindow(clip_import)

    def copyImport(self, event=None):
        selection: list[tuple[str, str]] = [
            (d['target_tag'], d['new_tag'])
            for d in self.tree_tags.getSelectionDicts()
        ]

        if len(selection) == 0:
            return

        clip_import = '\n'.join(
            f"{source}\n{ideal}"
            for (source, ideal) in selection
        )
        TextCopyWindow(clip_import)

    def deleteSelected(self, event=None):
        self.tree_tags.tree.delete(*self.tree_tags.tree.selection())


class RelationshipAdderWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """"""
    def __init__(self, suggestions: list[RelationshipAction], *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.suggestions: list[RelationshipAction] = suggestions

        self.title("Add tag relationships")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame_ra = RelationshipAdderFrame(self)
        frame_ra.grid(column=0, row=0, sticky="nsew")
        self.bind("<Delete>", frame_ra.deleteSelected)

        frame_ra.setSuggestions(self.suggestions)

        self.mainloop()