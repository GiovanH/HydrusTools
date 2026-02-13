import concurrent.futures
import logging
import pprint
import threading
import tkinter as tk
from tkinter import ttk

import hydrus_api
from PIL import ImageTk

from hydrustools import logic
from hydrustools.component.image_picker import ImageListFrame, ImagePickerWindow
from hydrustools.component.tageditorlist import TagEditorList

from ..component.gui_util import (
    Increment,
    SearchQueryEntry,
    TreeviewHeadings,
    pb_iter,
    tkwrap,
    tkwrapc,
)
from ..component.multicolumnlistbox import MultiColumnListbox
from ..component.toolwindow import ToolWindow
from ..settings import Settings

DEBUG_FAST_PICK = True

def debug_get_selection():
    resp = logic.client.search_files(
        tags=["meta:sfw", "source:newgrounds"] # type: ignore
    )
    matching_files = resp['file_ids']
    resp = logic.client.get_file_metadata(file_ids=matching_files, include_notes=True)
    return resp['metadata']

class ImageSearchWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """TODO"""
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.result: list[dict] | None = None
        self.textvar_query: tk.StringVar = Settings.boundTkVar(self, name='imagesearch_query')

        self.initwindow()

        self.mainloop()

    def initwindow(self):
        self.title("Image Search")
        self.geometry("970x570")

        self.rowconfigure(0, weight=1)
        # self.columnconfigure(0, weight=1)

        ccx = Increment()

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="ns")

            self.image_list = ImageListFrame(self, width=200)
            self.image_list.grid(column=cx.inc(), row=cy.inc(), in_=col)
            col.rowconfigure(cy.value, weight=1)

            self.image_list.table.tree.configure(
                columns=[],
                show="tree",
                selectmode=tk.BROWSE
            )
            # self.image_list.table.bindSelectionAction("<Button-1>", self.on_image_selected)
            self.image_list.table.bindSelectionActionUID("<Button-1>", self.on_image_selected)

            btn_open = ttk.Button(col, text="Pick Images", command=self.pick_images)
            btn_open.grid(column=cx.value, row=cy.inc(), sticky="ew")

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="nsew")
            self.columnconfigure(ccx.value, weight=1)

            self.tag_editor_list = TagEditorList(col)
            self.tag_editor_list.grid(column=cx.inc(), row=cy.inc(), sticky="nsew")
            col.columnconfigure(cx.value, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="ns")

            btn_open = ttk.Button(col, text="Pick Images", command=self.pick_images)
            btn_open.grid(column=cx.inc(), row=cy.inc(), sticky="ew")

    def pick_images(self, event=None):
        if DEBUG_FAST_PICK:
            selection = debug_get_selection()
        else:
            instance = ImagePickerWindow()
            self.wait_window(instance)
            selection: None | list[dict] = instance.result
        # selection = ImagePickerWindow.pick()

        if not selection:
            self.setStatus("Selection canceled")
            return
        self.setStatus(f"Selected {len(selection)} images")
        self.image_list.delete_all()
        for meta in selection:
            self.image_list.addItemFromMeta(meta)
        self.image_list.load_thumbnails()

    def on_image_selected(self, image_id):
        metadata = self.image_list.known_metadata[str(image_id)]
        self.set_image(metadata)

    def set_image(self, metadata):
        pprint.pprint(metadata)
        self.tag_editor_list.setTagList(metadata['tags'][logic.local_tags_service_key]['display_tags'].get(str(hydrus_api.TagStatus.CURRENT.value), []))