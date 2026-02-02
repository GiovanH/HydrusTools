import logging
import pprint
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from hydrustools import logic

from .gui_util import Increment, tkwrap, tkwrapc
from .multicolumnlistbox import MultiColumnListbox
from .toolwindow import ToolWindow

logging.basicConfig(level=logging.INFO)

@dataclass
class TagAction():
    file_id: int
    identifier: str
    new_tags: list[str]

HEAD_ID = "File ID"
HEAD_IDSTR = "Identifier"
HEAD_NEWTAGS = "New tags"

class TagAdderWindow(ToolWindow):
    helpstr = """Change this help string"""

    def __init__(self, tag_actions: list[TagAction], *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.logger.info(pprint.pformat(tag_actions))
        self.tag_actions: list[TagAction] = tag_actions

        self.table_headings = [
            HEAD_ID,
            HEAD_IDSTR,
            HEAD_NEWTAGS
        ]

        self.initwindow()
        self.focus()

        self.mainloop()

    def initwindow(self) -> None:
        self.title("Add Tags")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        # Right
        counter_main_row.inc()
        self.tree_tags = MultiColumnListbox(self, headers=self.table_headings)  # noqa: F821

        self.tree_tags.update_tree([
            {"id": i, "values": [ta.file_id, ta.identifier, ' '.join(ta.new_tags)]}
            for i, ta in enumerate(self.tag_actions)
        ])

        with tkwrap(self.tree_tags) as tree:
            # assert isinstance(tree, ttk.Treeview)
            tree.grid(column=0, row=counter_main_row.value, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as frame_bottom:
            frame_bottom.grid(row=counter_main_row.inc(), column=0, columnspan=2, sticky="ew")

            ttk.Label(frame_bottom, textvariable=self.textvar_status).grid(column=0, row=0, sticky="nsew")

            frame_bottom.columnconfigure(0, weight=1)

            btn_flatten = ttk.Button(frame_bottom, text="Open selected", command=self.openPage, width=40)
            btn_flatten.grid(column=1, row=0, sticky="nse")

            btn_flatten = ttk.Button(frame_bottom, text="Apply selected", command=self.applySelected, width=40)
            btn_flatten.grid(column=2, row=0, sticky="nse")

            btn_flatten = ttk.Button(frame_bottom, text="Apply all", command=self.applyAll, width=40)
            btn_flatten.grid(column=3, row=0, sticky="nse")

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
                self.setStatus(f"Added tags {ta.new_tags!r} to {ta.file_id}")
                self.tree_tags.tree.delete(self.tag_actions.index(ta))

    def openPage(self, event=None):
        selection = self.tree_tags.getSelectionIDs()
        if len(selection) == 0:
            return

        matching_ids = [
            self.tag_actions[int(i)].file_id
            for i in selection
        ]
        logic.client.add_popup("Tag Search", files_label=f"Selected Images", file_ids=matching_ids) # type: ignore
