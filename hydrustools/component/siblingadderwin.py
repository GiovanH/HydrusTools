import itertools
import logging
import pprint
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from hydrustools import logic

from .gui_util import Increment, ScrollableFrame, TextCopyWindow, flatList, tkwrap, tkwrapc
from .multicolumnlistbox import MultiColumnListbox
from .toolwindow import ToolWindow

logging.basicConfig(level=logging.INFO)

@dataclass
class SiblingAction():
    tag: str
    sibling_options: list[str]
    current_sibling: None | int
    group: str


class SiblingAdderWindow(ToolWindow):
    helpstr = """Change this help string"""

    def __init__(self, siblings: list[SiblingAction], *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.siblings: list[SiblingAction] = []
        for (key, group) in itertools.groupby(
            sorted(siblings, key = lambda sa: sa.group),
            key = lambda sa: sa.group
        ):
            self.siblings += [*group]

        self.values = [
            tk.StringVar(value=(
                sa.sibling_options[sa.current_sibling]
                if sa.current_sibling
                else ""
            ))
            for i, sa in enumerate(self.siblings)
        ]

        self.initwindow()
        self.focus()

        self.mainloop()

    def initwindow(self) -> None:
        self.title("Configure Siblings")
        self.geometry("440x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        # Right
        counter_main_row.inc()

        with tkwrapc(ScrollableFrame(self, relief=tk.GROOVE, padding=2)) as (sf, cx, cy):
            sf.grid(row=counter_main_row.inc(), column=0, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

            assert isinstance(sf, ScrollableFrame)
            frame: ttk.Frame = sf.container
            frame.columnconfigure(0, weight=1)
            frame.columnconfigure(1, weight=1)

            for i, sa in enumerate(self.siblings):
                label = ttk.Label(frame, text=sa.tag)
                label.grid(row=cy.inc(), column=0, sticky="e")

                # label = ttk.Label(frame, text=sa.group)
                # label.grid(row=cy.value, column=2, sticky="e")

                om = ttk.OptionMenu(frame, self.values[i], self.values[i].get(), *sa.sibling_options)
                om.grid(row=cy.value, column=1, sticky="we")

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as frame_bottom:
            frame_bottom.grid(row=counter_main_row.inc(), column=0, sticky="ew")

            ttk.Label(frame_bottom, textvariable=self.textvar_status).grid(column=0, row=0, sticky="nsew")

            frame_bottom.columnconfigure(0, weight=1)

            # btn_flatten = ttk.Button(frame_bottom, text="Open selected", command=self.openPage, width=40)
            # btn_flatten.grid(column=1, row=0, sticky="nse")

            btn_flatten = ttk.Button(frame_bottom, text="Map siblings", command=self.mapSiblings, width=40)
            btn_flatten.grid(column=2, row=0, sticky="nse")

            # btn_flatten = ttk.Button(frame_bottom, text="Apply all", command=self.applyAll, width=40)
            # btn_flatten.grid(column=3, row=0, sticky="nse")

    def mapSiblings(self, event=None):

        clip_import = ""
        for i, sa in enumerate(self.siblings):
            selection = self.values[i].get()
            if not selection:
                continue
            for candidate in sa.sibling_options:
                if candidate == selection:
                    continue
                if sa.current_sibling and sa.sibling_options[sa.current_sibling] == selection:
                    continue
                clip_import += f"{candidate}\n{selection}\n"

        TextCopyWindow(clip_import)

    # def applySelected(self, event=None):
    #     # selection = [
    #     #     (row['Source Tag'], row['Ideal'])
    #     #     for row in (self.tree_tags.set(child) for child in self.tree_tags.selection())
    #     # ]
    #     self.logger.info(self.tree_tags.tree.selection())
    #     self.logger.info(self.tree_tags.getSelectionDicts())
    #     selection = self.tree_tags.getSelectionIDs()

    #     if len(selection) == 0:
    #         return

    #     self.logger.info(selection)
    #     actions = [
    #         self.tag_actions[int(i)]
    #         for i in selection
    #     ]

    #     self.applyActions(actions)

    # def applyAll(self, event=None):
    #     self.applyActions(self.tag_actions)

    # def applyActions(self, actions):
    #     explaination = '\n'.join(f'{a}' for a in actions)
    #     user_confirmed = messagebox.askyesno(
    #         title="Confirm",
    #         message=f"{explaination}\n\nAdd tags to files?"
    #     )
    #     if user_confirmed:
    #         for ta in actions:
    #             logic.client.add_tags(
    #                 file_ids=[ta.file_id],
    #                 service_keys_to_tags={
    #                     logic.local_tags_service_key: ta.new_tags,
    #                 }
    #             )
    #             self.setStatus(f"Added tags {ta.new_tags!r} to {ta.file_id}")
    #             self.tree_tags.tree.delete(self.tag_actions.index(ta))

    # def openPage(self, event=None):
    #     selection = self.tree_tags.getSelectionIDs()
    #     if len(selection) == 0:
    #         return

    #     matching_ids = [
    #         self.tag_actions[int(i)].file_id
    #         for i in selection
    #     ]
    #     logic.client.add_popup("Tag Search", files_label=f"Selected Images", file_ids=matching_ids) # type: ignore
