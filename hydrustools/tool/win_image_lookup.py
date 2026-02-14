import pprint
import tkinter as tk
from tkinter import ttk

import hydrus_api

from .. import logic
from ..logic import FileMetadata
from hydrustools.component.image_picker import ImageListFrame, ImagePickerWindow
from hydrustools.component.tageditorlist import TagEditorList

from ..component.gui_util import (
    Increment,
    tkwrapc,
)
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

class ImageMetadataLookupWin(ToolWindow):  # noqa: PLR0904
    helpstr = """TODO"""
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.current_image: None | FileMetadata = None
        self.result: list[FileMetadata] | None = None
        self.textvar_query: tk.StringVar = Settings.boundTkVar(self, name='imagesearch_query')

        self.initwindow()

        self.mainloop()

    def initwindow(self):
        self.title("Image Metadata Lookup")
        self.geometry("1040x590")

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

            lab = ttk.Label(master=col, text="Metadata Services")
            lab.grid(column=cx.inc(), row=cy.inc(), sticky="ew")

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="nsew")
            self.columnconfigure(ccx.value, weight=1)

            col.columnconfigure(0, weight=1)

            lab = ttk.Label(col, text="Hydrus Image", anchor='center')
            lab.grid(column=0, row=cy.inc(), sticky="ew")

            self.tag_editor_list = TagEditorList(col)
            self.tag_editor_list.grid(column=0, row=cy.inc(), sticky="nsew")
            col.rowconfigure(cy.value, weight=1)

            btn_merge = ttk.Button(col, text="Save Tags", command=self.save_tag_list)
            btn_merge.grid(column=0, row=cy.inc(), sticky="ew")

        with tkwrapc(ttk.Frame(self)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="nsew")
            self.columnconfigure(ccx.value, weight=0)

            with tkwrapc(ttk.Frame(col, relief=tk.GROOVE)) as (row, crx, cry):
                row.grid(column=0, row=cy.inc(), sticky="nsew")
                col.rowconfigure(cy.value, weight=1)
                col.columnconfigure(0, weight=1)

                lab = ttk.Label(row, text="Source URLs")
                lab.grid(column=crx.inc(), row=cry.inc(), sticky="ew")

                self.text_current_urls = tk.Text(row, width=60, font=('Courier', 9))
                self.text_current_urls.grid(column=crx.value, row=cry.inc(), sticky="ew")

            with tkwrapc(ttk.Frame(col, relief=tk.GROOVE)) as (row, crx, cry):
                row.grid(column=0, row=cy.inc(), sticky="nsew")
                col.rowconfigure(cy.value, weight=1)
                col.columnconfigure(0, weight=1)

                lab = ttk.Label(row, text="Notes")
                lab.grid(column=crx.inc(), row=cry.inc(), sticky="ew")

                self.text_current_notes = tk.Text(row, width=60, font=('Courier', 9))
                self.text_current_notes.grid(column=crx.value, row=cry.inc(), sticky="ew")


        with tkwrapc(ttk.Frame(self)) as (row, cx, cy):
            row.grid(column=0, row=1, columnspan=ccx.inc(), sticky="ew")

            self.pb = ttk.Progressbar(row, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=cx.inc(), row=0, sticky="ns")

            ttk.Label(row, textvariable=self.textvar_status).grid(column=cx.inc(), row=0, sticky="nsew")
            row.columnconfigure(cx.value, weight=1)

    def save_tag_list(self):
        if not self.current_image:
            self.logger.error("Can't set tags, no image selected")
            return
        logic.set_tag_list_of_images(
            tag_list=self.tag_editor_list.tag_list,
            tool=self,
            metadata_list=[self.current_image]
        )
        self.refresh_image(self.current_image['file_id'])

    def pick_images(self, event=None):
        if DEBUG_FAST_PICK:
            selection = debug_get_selection()
        else:
            instance = ImagePickerWindow()
            self.wait_window(instance)
            selection: None | list[FileMetadata] = instance.result
        # selection = ImagePickerWindow.pick()

        if not selection:
            self.setStatus("Selection canceled")
            return
        self.setStatus(f"Opened list of {len(selection)} images")
        self.image_list.delete_all()
        for meta in selection:
            self.image_list.addItemFromMeta(meta)
        self.image_list.load_thumbnails()

    def refresh_image(self, image_id):
        new_metadata = logic.client.get_file_metadata(
            file_ids=[image_id]
        )['metadata'][0]
        self.image_list.known_metadata[str(image_id)] = new_metadata
        self.set_image(new_metadata)

    def on_image_selected(self, image_id):
        metadata = self.image_list.known_metadata[str(image_id)]
        self.set_image(metadata)

    def set_image(self, metadata: logic.FileMetadata):
        pprint.pprint(metadata)
        self.current_image = metadata

        pprint.pprint(metadata)

        self.tag_editor_list.setTagList(metadata['tags'][logic.local_tags_service_key]['display_tags'].get(str(hydrus_api.TagStatus.CURRENT.value), []))

        self.text_current_urls.configure(state=tk.NORMAL)
        self.text_current_urls.delete("1.0", tk.END)
        self.text_current_urls.insert(tk.END, '\n'.join(metadata['known_urls']))
        self.text_current_urls.configure(state=tk.DISABLED)

        self.text_current_notes.configure(state=tk.NORMAL)
        self.text_current_notes.delete("1.0", tk.END)
        self.text_current_notes.insert(tk.END, pprint.pformat(metadata['notes'], width=60))
        self.text_current_notes.configure(state=tk.DISABLED)