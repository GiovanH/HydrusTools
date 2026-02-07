import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from ..component.gui_util import Increment, tkwrap
from ..component.multicolumnlistbox import MultiColumnListbox
from ..component.toolwindow import ToolWindow
from ..settings import HTSettings
from .gui_util import TextCopyWindow

logging.basicConfig(level=logging.INFO)

@dataclass
class RelationshipAction():
    target_tag: str
    new_tag: str
    note: str

HEAD_TAG_A = "Source tag"
HEAD_TAG_B = "New relationship"
HEAD_TAG_COMMENT = "Note"


Settings = HTSettings()


class RelationshipAdderWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """Flatten tag siblings.

In effect, this finds all images with the source tag directly specified and replaces that with the ideal tag as defined by the sibling relationship.

Select the specific relationships to flatten and click the flatten button to commit changes.

Presearch searches Hydrus for tags (* will only work if specified in the tag repo settings). Refinement filters that list to only tags matching the given expression. Presearch is fastest!
    """
    def __init__(self, suggestions: list[RelationshipAction], *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.table_headings = [HEAD_TAG_A, HEAD_TAG_B, HEAD_TAG_COMMENT]
        self.suggestions: list[RelationshipAction] = suggestions

        self.initwindow()

        self.mainloop()

    def initwindow(self) -> None:
        self.title("Add tag relationships")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        # Right
        counter_main_row.inc()
        self.tree_tags = MultiColumnListbox(self, headers=self.table_headings)

        with tkwrap(self.tree_tags) as tree:
            # assert isinstance(tree, ttk.Treeview)
            tree.grid(column=0, row=counter_main_row.value, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

        for si in sorted(self.suggestions, key=lambda si: si.target_tag):
            row = [si.target_tag, si.new_tag, si.note]
            # self.tree_tags.insert('', tk.END, values=row)
            self.tree_tags.insert_item({"values": row})

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as frame_bottom:
            frame_bottom.grid(row=counter_main_row.inc(), column=0, columnspan=2, sticky="ew")

            ttk.Label(frame_bottom, textvariable=self.textvar_status).grid(column=0, row=0, sticky="nsew")

            frame_bottom.columnconfigure(0, weight=1)

            btn_flatten = ttk.Button(frame_bottom, text="Copy Import for selected", command=self.copyImport, width=40)
            btn_flatten.grid(column=1, row=0, sticky="nse")

            btn_flatten = ttk.Button(frame_bottom, text="Copy Import", command=self.copyImportAll, width=40)
            btn_flatten.grid(column=2, row=0, sticky="nse")


        self.bind("<Delete>", self.deleteSelected)

    def copyImportAll(self, event=None):
        selection: list[tuple[str, str]] = [
            (d.target_tag, d.new_tag)
            for d in self.suggestions
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
            (d[HEAD_TAG_A], d[HEAD_TAG_B])
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