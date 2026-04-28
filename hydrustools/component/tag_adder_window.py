import dataclasses
import logging
import tkinter as tk
from collections import OrderedDict
from dataclasses import dataclass
from functools import partial
from tkinter import messagebox, ttk
from typing import ClassVar, Iterator
import itertools

from hydrustools.component.HydrusImageTable import HydrusImageTable
from hydrustools.utils import hydrus

from ..utils.gui_util import Increment, pb_iter, tkwrap
from .multicolumnlistbox import TreeListItemDict, TreeviewSchema
from .toolwindow import ToolWindow


@dataclass
class TagAction():
    file_id: int
    identifier: str
    new_tags: list[str]

@dataclass
class TagActionGrouped():
    file_ids: list[int]
    new_tags: list[str]
    tag_actions: list[TagAction]

def group_tag_actions(actions: list[TagAction]) -> Iterator[TagActionGrouped]:
    key = lambda a: a.new_tags
    sorted_actions = sorted(actions, key=key)
    for tags, group in itertools.groupby(sorted_actions, key=key):
        group_list = list(group)
        yield TagActionGrouped(
            file_ids=[a.file_id for a in group_list],
            new_tags=tags,
            tag_actions=group_list,
        )

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
        self.pb: None | ttk.Progressbar = None

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
        self.tree_tags = HydrusImageTable(self, toolmaster=self.toolmaster, schema=TagActionSchema)

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

                self.pb = ttk.Progressbar(frame_bottom, orient='vertical',
                    mode='determinate',
                    length=30
                )
                self.pb.grid(column=0, row=0, sticky="ns")

                ttk.Label(frame_bottom, textvariable=self.toolmaster.textvar_status).grid(column=1, row=0, sticky="nsew")

                frame_bottom.columnconfigure(1, weight=1)

                self.btn_open_sel(frame_bottom).grid(column=2, row=0, sticky="nse")

                self.btn_apply_sel(frame_bottom).grid(column=3, row=0, sticky="nse")

                self.btn_apply_all(frame_bottom).grid(column=4, row=0, sticky="nse")

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

    def applyActions(self, actions: list[TagAction]):

        grouped_actions = [*group_tag_actions(actions)]

        explaination = '\n'.join(f'{a}' for a in grouped_actions[:60])
        user_confirmed = messagebox.askyesno(
            title="Confirm",
            message=f"{explaination}\n\nAdd tags to files?"
        )
        if user_confirmed:
            for ga in pb_iter(self.pb or getattr(self.toolmaster, 'pb', None) or {}, grouped_actions):
                hydrus.client.add_tags(
                    file_ids=ga.file_ids,
                    service_keys_to_tags={
                        hydrus.local_tags_service_key: ga.new_tags,
                    }
                )
                self.toolmaster.setStatus(f"Added tags {ga.new_tags!r} to {ga.file_ids}")
                for ta in ga.tag_actions:
                    self.tree_tags.tree.delete(self.tag_actions.index(ta))

    def openPage(self, event=None):
        selection = self.tree_tags.getSelectionIDs()
        if len(selection) == 0:
            return

        matching_ids = [
            self.tag_actions[int(i)].file_id
            for i in selection
        ]
        hydrus.client.add_popup("Tag Search", files_label="Selected Images", file_ids=matching_ids) # type: ignore

    def deleteSelected(self, event=None):
        self.tree_tags.tree.delete(*self.tree_tags.tree.selection())

    def load_thumbnails(self):
        self.tree_tags.load_thumbnails()

class TagAdderWindow(ToolWindow):
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
            frame_ta.add_item(ta, thumb=False)

        frame_ta.load_thumbnails()

        self.focus()
        self.mainloop()