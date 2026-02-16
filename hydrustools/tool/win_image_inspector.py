from collections import OrderedDict
import pprint
import tkinter as tk
from tkinter import ttk
from typing import ClassVar

import hydrus_api

from hydrustools.component.HydrusImageTable import HydrusImageTable
from hydrustools.component.image_canvas import ContentCanvas
from hydrustools.component.multicolumnlistbox import TreeListItemDict, TreeviewSchema

from .. import logic
from ..logic import FileMetadata
from hydrustools.component.image_picker import ImageListFrame, ImagePickerWindow
from hydrustools.component.tageditorlist import TagEditorList

from ..component.gui_util import (
    Increment,
    get_selection_neighbors,
    mod_selection,
    pb_iter,
    tkwrapc,
)
from ..component.toolwindow import ToolWindow

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
    resp = logic.client.search_files(
        # tags=["meta:sfw", "source:e621"] # type: ignore
        tags=["system:inbox", "system:filetype is image", "system:limit=128"]
    )
    matching_files = resp['file_ids']
    # print(matching_files)
    resp = logic.client.get_file_metadata(file_ids=matching_files, include_notes=True)
    return resp['metadata']

class ImageInspectorWin(ToolWindow):
    helpstr = """TODO"""
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.current_image: None | FileMetadata = None
        self.result: list[FileMetadata] | None = None
        self.refreshing: bool = False

        self.textvar_info = tk.StringVar(self, "No image selected")

        self.initwindow()
        self.bind_controls()

        self.known_metadata: dict[int, FileMetadata] = {}

        self.after_idle(self.pick_images)

        self.mainloop()

    def initwindow(self):
        self.title("Image Search")
        self.geometry("1400x610")

        self.rowconfigure(0, weight=1)

        ccx = Increment()

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="ns")

            self.image_list = HydrusImageTable(self, schema=ImageIconSchema)
            self.image_list.grid(column=cx.inc(), row=cy.inc(), in_=col)
            col.rowconfigure(cy.value, weight=1)

            self.image_list.tree.configure(
                show="tree",
                selectmode=tk.BROWSE
            )

            self.image_list.tree.bind("<<TreeviewSelect>>", self.on_image_selected)

            btn_open = ttk.Button(col, text="Pick Images", command=self.pick_images)
            btn_open.grid(column=cx.value, row=cy.inc(), sticky="ew")

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8, width=350)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="nsew")

            self.tag_editor_list = TagEditorList(col)
            self.tag_editor_list.grid(column=0, row=cy.inc(), sticky="nsew")
            col.rowconfigure(cy.value, weight=1)
            col.columnconfigure(0, weight=1, minsize=200)

            # self.btn_save_tags = ttk.Button(col, text="Save Tags", command=self.save_tag_list)
            # self.btn_save_tags.grid(column=0, row=cy.inc(), sticky="ew")

        with tkwrapc(ttk.Frame(self)) as (row, cx, cy):
            row.grid(column=0, row=1, columnspan=ccx.inc(), sticky="ew")

            self.pb = ttk.Progressbar(row, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=cx.inc(), row=0, sticky="ns")

            ttk.Label(row, textvariable=self.textvar_status).grid(column=cx.inc(), row=0, sticky="nsew")
            row.columnconfigure(cx.value, weight=1)

        with tkwrapc(ttk.Frame(self)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, rowspan=2, sticky="nsew")
            self.columnconfigure(ccx.value, weight=1)

            self.canvas = ContentCanvas(col, width=800, height=800)
            self.canvas.grid(column=0, row=0, sticky="nsew")
            col.columnconfigure(index=0, weight=1)
            col.rowconfigure(index=0, weight=1)

        with tkwrapc(ttk.PanedWindow(self)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, rowspan=2, sticky="nsew")


            with tkwrapc(ttk.Frame(col, relief=tk.GROOVE)) as (row, crx, cry):
                row.grid(column=0, row=cy.inc(), sticky="nsew")
                col.rowconfigure(cy.value, weight=1)
                col.columnconfigure(0, weight=1)

                lab = ttk.Label(row, textvariable=self.textvar_info, width=40, wraplength=250)
                lab.grid(column=crx.inc(), row=cry.inc(), sticky="ew")

            with tkwrapc(ttk.Frame(col, relief=tk.GROOVE)) as (row, crx, cry):
                row.grid(column=0, row=cy.inc(), sticky="sew")

                btn_refresh = ttk.Button(row, text="Refresh", command=self.refresh_current)
                btn_refresh.grid(column=crx.inc(), row=cry.inc(), sticky="ew")


            # self.columnconfigure(ccx.value, weight=1)

            # self.canvas = ContentCanvas(col, width=800, height=800)
            # self.canvas.grid(column=0, row=0, sticky="nsew")
            # col.columnconfigure(index=0, weight=1)
            # col.rowconfigure(index=0, weight=1)

    def next_image(self):
        mod_selection(self.image_list.tree, prev=0, next=1)

    def prev_image(self):
        mod_selection(self.image_list.tree, prev=1, next=0)

    def bind_controls(self):
        entry: tk.Entry = self.tag_editor_list.entry_add

        self.tag_editor_list.bind("<<Modified>>", self.configure_visual)

        self.image_list.tree.configure(takefocus=False)


        entry.bind("<Right>", lambda e: entry.get() == "" and self.next_image())
        entry.bind("<Left>", lambda e: entry.get() == "" and self.prev_image())

        entry.bind("<Control-e>", self.toggle_keep)
        entry.bind("<Control-d>", self.toggle_delete)

        self.tag_editor_list.bind("<<DWIM>>", self.entry_dwim)

        entry.focus()

    def entry_dwim(self, event=None):
        edited = False
        # if self.tag_editor_list.modified:
        #     self.save_tag_list()
        #     edited = True

        if self.current_image and self.current_image['is_inbox'] and not self.current_image['is_deleted']:
            self.toggle_keep()
            edited = True

        if not edited:
            self.next_image()

    def save_tag_list(self):
        if not self.current_image:
            self.logger.error("Can't set tags, no image selected")
            return
        try:
            logic.set_tag_list_of_images(
                tag_list=self.tag_editor_list.tag_list,
                tool=self,
                metadata_list=[self.current_image]
            )
            self.setStatus("Saved tag changes")
            self.fetch_metadata_and_open(self.current_image['file_id'])
        except TypeError as e:
            self.logger.exception(f"Couldn't apply tag list: {self.tag_editor_list.tag_list=}, {self.tag_editor_list.modified}")
            raise e

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
            self.image_list.insert_item(ImageIconSchema.to_tree_item(meta))
        self.fetch_all_metadata()

        first_file_id = selection[0]["file_id"]
        self.image_list.tree.selection_set(first_file_id)
        self.image_list.tree.see(first_file_id)

        self.image_list.load_thumbnails()

    def fetch_all_metadata(self):
        all_ids = map(int, self.image_list.getAllIds())

        for id_chunk in pb_iter(self.pb, [*logic.chunk(all_ids, 200)]):
            resp = logic.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

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
        self.fetch_metadata_and_open(self.current_image['file_id'])
        self.setStatus("Refreshed metadata from server")

    def fetch_metadata_and_open(self, image_id):
        self.logger.info(f"Refreshing metadata for {image_id}")
        new_metadata = logic.client.get_file_metadata(
            file_ids=[image_id],
            include_notes=True
        )['metadata'][0]
        # pprint.pprint(new_metadata)
        self.known_metadata[image_id] = new_metadata
        self.set_image(new_metadata)

    def on_image_selected(self, event: tk.Event):
        widget: ttk.Treeview = event.widget # type: ignore
        image_id = int(widget.selection()[0])
        if not image_id:
            self.logger.warning("Called on_image_selected with no selected image")
            return
        metadata = self.known_metadata[image_id]
        self.set_image(metadata)

        for neighbor_id in get_selection_neighbors(widget):
            self.canvas.preload_image(self.known_metadata[int(neighbor_id)])

    def set_image(self, metadata: logic.FileMetadata):
        self.current_image = metadata

        self.update_text_info()

        self.canvas.set_image(metadata)

        self.refreshing = True
        tag_list = metadata['tags'][logic.local_tags_service_key]['display_tags'].get(str(hydrus_api.TagStatus.CURRENT.value), [])
        self.tag_editor_list.setTagList(tag_list)

        self.tag_editor_list.modified = False
        self.refreshing = False
        self.configure_visual()


    def update_text_info(self):
        metadata = self.current_image
        if not metadata:
            self.textvar_info.set("No image selected")
            return

        lines = []

        # pprint.pprint(metadata)

        if metadata['is_inbox']:
            lines.append("Inbox")
            lines.append("")
        else:
            lines.append("Archived")
            lines.append("")

        if metadata['is_trashed']:
            lines.append("Trashed")
            lines.append("")

        if len(metadata['known_urls']) > 0:
            lines.append("URLs:")
            lines.extend(metadata['known_urls'])
            lines.append("")

        for title, body in metadata['notes'].items():
            lines.append(f"{title}:")
            lines.append(body)
            lines.append("")

        self.textvar_info.set(value='\n'.join(lines))

    def configure_visual(self, event=None):
        # Actually, just autosave
        if not self.refreshing and self.tag_editor_list.modified:
            self.save_tag_list()

        return

        if self.tag_editor_list.modified:
            # self.setStatus(f"Modified {self.tag_editor_list.modified}, bad")
            self.btn_save_tags.configure(state=tk.ACTIVE)
        else:
            # self.setStatus(f"Modified {self.tag_editor_list.modified}, normal")
            self.btn_save_tags.configure(state=tk.DISABLED)


        # self.text_current_urls.configure(state=tk.NORMAL)
        # self.text_current_urls.delete("1.0", tk.END)
        # self.text_current_urls.insert(tk.END, '\n'.join(metadata['known_urls']))
        # self.text_current_urls.configure(state=tk.DISABLED)

    def toggle_keep(self, event=None):
        metadata = self.current_image
        if not metadata:
            self.textvar_info.set("No image selected")
            return

        file_id = metadata['file_id']

        if metadata['is_inbox']:
            logic.client.archive_files(file_ids=[file_id])
            self.setStatus(f"Moved file {file_id} to archive")
        else:
            logic.client.unarchive_files(file_ids=[file_id])
            self.setStatus(f"Moved file {file_id} to inbox")

        if self.tag_editor_list.modified:
            self.save_tag_list()
        self.refresh_current()


    def toggle_delete(self, event=None):
        metadata = self.current_image
        if not metadata:
            self.textvar_info.set("No image selected")
            return

        file_id = metadata['file_id']

        if metadata['is_trashed']:
            logic.client.undelete_files(file_ids=[file_id])
            self.setStatus(f"Removed file {file_id} from trash")
        else:
            logic.client.delete_files(file_ids=[file_id])
            self.setStatus(f"Moved file {file_id} to trash")

        if self.tag_editor_list.modified:
            self.save_tag_list()
        self.refresh_current()