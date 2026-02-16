from collections import OrderedDict
import dataclasses
from functools import partial
import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import ClassVar

from hydrustools import logic
from hydrustools.component.HydrusImageTable import HydrusImageTable

from .gui_util import Increment, tkwrap
from .multicolumnlistbox import TreeListItemDict, TreeviewSchema
from .toolwindow import ToolWindow



@dataclass
class TagAction():
    file_id: int
    identifier: str
    new_tags: list[str]

# HEAD_ID = "File ID"
# HEAD_IDSTR = "Identifier"
# HEAD_NEWTAGS = "New tags"

# TODO: Use image_picker for images

class TagActionSchema(TreeviewSchema[TagAction]):
    headers: ClassVar[OrderedDict[str, str | None]] = OrderedDict([
        ('file_id', None),
        ('identifier', 'Identifier'),
        ('new_tags', 'New Tags'),
    ])
    imagesize = (100, 100)

    @staticmethod
    def to_tree_item(item: TagAction) -> TreeListItemDict:
        return {
            "values": [*dataclasses.astuple(item)]
        }

class TagAdderFrame(ttk.Frame):
    helpstr = """Change this help string"""

    def __init__(self, master: ToolWindow, pack_buttons=True, *args_, **kwargs) -> None:
        super().__init__(master=master, *args_, **kwargs)

        self.toolmaster: ToolWindow = master
        self.logger: logging.Logger = master.logger

        self.pack_buttons = pack_buttons

        # self.logger.info(pprint.pformat(tag_actions))
        self.tag_actions: list[TagAction] = []

        self.initwindow(pack_buttons=pack_buttons)

    def delete_all(self):
        # self.suggestions.clear()
        self.tree_tags.delete_all()

    def add_item(self, ta: TagAction, thumb=True):
        # self.tree_tags.insert('', tk.END, values=row)
        self.tag_actions.append(ta)
        i = self.tag_actions.index(ta)

        tkid = self.tree_tags.insert_item({
            "id": i,
            **TagActionSchema.to_tree_item(ta)
        })
        # self.suggestions.append(si)

        if thumb:
            self.tree_tags.addItemThumb(tkid=tkid, file_id=ta.file_id)

    def initwindow(self, pack_buttons: bool) -> None:
        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        # Right
        counter_main_row.inc()
        self.tree_tags = HydrusImageTable(self, toolmaster=self.toolmaster, schema=TagActionSchema)  # noqa: F821

        with tkwrap(self.tree_tags) as tree:
            # assert isinstance(tree, ttk.Treeview)
            tree.grid(column=0, row=counter_main_row.value, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

        self.btn_open_sel = partial(ttk.Button, text="Open selected", command=self.openPage, width=25)
        self.btn_apply_sel = partial(ttk.Button, text="Apply selected", command=self.applySelected, width=25)
        self.btn_apply_all = partial(ttk.Button, text="Apply all", command=self.applyAll, width=25)

        if pack_buttons:
            with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as frame_bottom:
                frame_bottom.grid(row=counter_main_row.inc(), column=0, columnspan=2, sticky="ew")

                ttk.Label(frame_bottom, textvariable=self.toolmaster.textvar_status).grid(column=0, row=0, sticky="nsew")

                frame_bottom.columnconfigure(0, weight=1)

                self.btn_open_sel(frame_bottom).grid(column=1, row=0, sticky="nse")

                self.btn_apply_sel(frame_bottom).grid(column=2, row=0, sticky="nse")

                self.btn_apply_all(frame_bottom).grid(column=3, row=0, sticky="nse")

    def applySelected(self, event=None):
        # selection = [
        #     (row['Source Tag'], row['Ideal'])
        #     for row in (self.tree_tags.set(child) for child in self.tree_tags.selection())
        # ]
        self.logger.info(self.tree_tags.tree.selection())
        self.logger.info(self.tree_tags.getSelectionDicts())
        selection = self.tree_tags.getSelectionIDs()

        if len(selection) == 0:
            return

        self.logger.info(selection)
        actions = [
            self.tag_actions[int(i)]
            for i in selection
        ]

        self.applyActions(actions)

    def applyAll(self, event=None):
        self.applyActions(self.tag_actions)

    def applyActions(self, actions):
        explaination = '\n'.join(f'{a}' for a in actions)
        user_confirmed = messagebox.askyesno(
            title="Confirm",
            message=f"{explaination}\n\nAdd tags to files?"
        )
        if user_confirmed:
            for ta in actions:
                logic.client.add_tags(
                    file_ids=[ta.file_id],
                    service_keys_to_tags={
                        logic.local_tags_service_key: ta.new_tags,
                    }
                )
                self.toolmaster.setStatus(f"Added tags {ta.new_tags!r} to {ta.file_id}")
                self.tree_tags.tree.delete(self.tag_actions.index(ta))

    def openPage(self, event=None):
        selection = self.tree_tags.getSelectionIDs()
        if len(selection) == 0:
            return

        matching_ids = [
            self.tag_actions[int(i)].file_id
            for i in selection
        ]
        logic.client.add_popup("Tag Search", files_label="Selected Images", file_ids=matching_ids) # type: ignore

    def deleteSelected(self, event=None):
        self.tree_tags.tree.delete(*self.tree_tags.tree.selection())

class TagAdderWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """"""
    def __init__(self, tag_actions: list[TagAction], *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.tag_actions: list[TagAction] = tag_actions

        self.title("Add tags")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        frame_ta = TagAdderFrame(self)
        frame_ta.grid(column=0, row=0, sticky="nsew")
        self.bind("<Delete>", frame_ta.deleteSelected)

        for ta in tag_actions:
            frame_ta.add_item(ta)

        self.focus()
        self.mainloop()