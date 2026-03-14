import tkinter as tk
from collections import OrderedDict
from tkinter import ttk
from typing import Any, ClassVar

from ..component.HydrusImageTable import HydrusImageTable
from ..component.image_picker import ImagePickerWindow
from ..component.multicolumnlistbox import TreeListItemDict, TreeviewSchema
from ..component.toolwindow import ToolWindow

from ..utils import hydrus
from ..utils.gui_util import (
    mod_selection,
    pb_iter,
    tkwrapc,
)

from ..utils.hydrus import FileMetadata

DEBUG_FAST_PICK = False

class ImageIconSchema(TreeviewSchema[FileMetadata]):
    headers: ClassVar[OrderedDict[str, str | None]] = OrderedDict([
        ('file_id', None),
    ])
    imagesize = (100, 100)

    @staticmethod
    def to_tree_item(item: FileMetadata) -> TreeListItemDict:
        return {
            "id": item['file_id'],
            "values": [item['file_id']]
        }

def debug_get_selection():
    resp = hydrus.client.search_files(
        # tags=["meta:sfw", "source:e621"] # type: ignore
        tags=["-creator:*", "system:has url with class e621 file page", "system:limit=50"]
    )
    matching_files = resp['file_ids']
    # print(matching_files)
    resp = hydrus.client.get_file_metadata(file_ids=matching_files, include_notes=True)
    return resp['metadata']


class ImageTool(ToolWindow):
    """Wrapper for ToolWindows that operate on individual images."""

    schema = ImageIconSchema
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.image_list: HydrusImageTable
        self.pb: ttk.Progressbar

        self.current_image: None | FileMetadata = None
        self.known_metadata: dict[int, FileMetadata] = {}

        self.get_file_metadata_kwargs: dict[str, Any] = {
            "include_notes": True,
            "detailed_url_information": False
        }

    def fac_image_list(self, master, *args, **kwargs) -> HydrusImageTable:
        self.image_list = HydrusImageTable(master, toolmaster=self, schema=self.schema, *args, **kwargs)

        self.image_list.tree.configure(
            show="tree",
            selectmode=tk.BROWSE
        )

        self.image_list.tree.bind("<<TreeviewSelect>>", self.on_image_selected)

        return self.image_list

    def fac_image_list_frame(self, master) -> ttk.Frame:
        with tkwrapc(ttk.Frame(master, relief=tk.GROOVE, padding=8)) as (col, cx, cy):
            assert isinstance(col, ttk.Frame)

            self.image_list = self.fac_image_list(col)
            self.image_list.grid(column=cx.inc(), row=cy.inc())
            col.rowconfigure(cy.value, weight=1)

            btn_open = ttk.Button(col, text="Pick Images", command=self.pick_images)
            btn_open.grid(column=cx.value, row=cy.inc(), sticky="ew")

            return col

    def next_image(self):
        mod_selection(self.image_list.tree, prev=0, next=1)

    def prev_image(self):
        mod_selection(self.image_list.tree, prev=1, next=0)

    def pick_images(self, event=None):
        if DEBUG_FAST_PICK:
            selection = debug_get_selection()
        else:
            instance = ImagePickerWindow(master=self, include_notes=True)
            self.wait_window(instance)
            selection: None | list[FileMetadata] = instance.result

        if not selection:
            self.setStatus("Selection canceled")
            return
        self.setStatus(f"Opened list of {len(selection)} images")
        self.image_list.delete_all()
        for meta in selection:
            self.image_list.insert_item(self.schema.to_tree_item(meta))
        self.fetch_all_metadata()

        first_file_id = selection[0]["file_id"]
        self.image_list.tree.selection_set(first_file_id)
        self.image_list.tree.see(first_file_id)

        self.image_list.load_thumbnails()

    def fetch_all_metadata(self):
        all_ids = map(int, self.image_list.getAllIds())

        for id_chunk in pb_iter(self.pb, [*hydrus.chunk(all_ids, 200)]):
            resp = hydrus.client.get_file_metadata(file_ids=id_chunk, **self.get_file_metadata_kwargs)

            def commit(resp=resp):
                for metadata in resp['metadata']:
                    # pprint.pprint(metadata)
                    file_id: int = metadata['file_id']
                    self.known_metadata[file_id] = metadata

            self.after('idle', commit)

    def refresh_current(self, event=None):
        if not self.current_image:
            self.setStatus("No current image")
            return
        image_id = self.current_image['file_id']
        self.logger.info(f"Refreshing metadata for {image_id}")
        self.fetch_metadata_for_image(image_id)
        self.setStatus("Refreshed metadata from server")
        self.set_image(self.known_metadata[image_id])

    def set_image(self, metadata: hydrus.FileMetadata):
        self.current_image = metadata

    def fetch_metadata_for_image(self, image_id):
        new_metadata = hydrus.client.get_file_metadata(
            file_ids=[image_id],
            include_notes=True
        )['metadata'][0]
        # pprint.pprint(new_metadata)
        self.known_metadata[image_id] = new_metadata

    def on_image_selected(self, event: tk.Event):
        widget: ttk.Treeview = event.widget # type: ignore
        image_id = int(widget.selection()[0])
        if not image_id:
            self.logger.warning("Called on_image_selected with no selected image")
            return
        metadata = self.known_metadata[image_id]
        self.set_image(metadata)
