import pprint
import tkinter as tk
from collections import OrderedDict
from tkinter import ttk
from typing import ClassVar

import hydrus_api

from hydrustools.component.HydrusImageTable import HydrusImageTable
from hydrustools.component.image_canvas import ContentCanvas
from hydrustools.component.image_picker import ImageListFrame, ImagePickerWindow
from hydrustools.component.imagetool import ImageIconSchema, ImageTool
from hydrustools.component.multicolumnlistbox import TreeListItemDict, TreeviewSchema
from hydrustools.component.tageditorlist import TagEditorList
from hydrustools.settings import Settings

from .. import logic
from ..component.gui_util import (
    Increment,
    get_selection_neighbors,
    grooveframe,
    mod_selection,
    pb_iter,
    tkwrap,
    tkwrapc,
)
from ..component.toolwindow import ToolWindow
from ..logic import FileMetadata


class ImageInspectorWin(ImageTool):
    label = "Image Inspector"
    helpstr = """Manually tag images and edit metadata.

First, select a group of images with the image search window. You can edit the current selection by clicking "Pick Images".

Focus the text entry field under "Add Tags" for fully-automatic operation:

Left/Right: Navigate
F5: Refresh all metadata
Ctrl-E: Toggle archive/inbox
Ctrl-D: Toggle trashed
Return: DWIM

Adjust Do What I Mean behavior using the checkboxes on the right-hand panel.

Type in the box to fuzzy-search for tags. Tag changes autosave if Autosave is checked, otherwise you will need to click Save, or use a DWIM action.

Fuzzy-search notes:
Tags
If tagname is attached to the image, "-tagname" will remove it.
"""
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.result: list[FileMetadata] | None = None
        self.refreshing: bool = False

        self.textvar_info = tk.StringVar(self, "No image selected")

        self.pref_autosave = Settings.boundTkVar(self, 'img_autosave', tk.BooleanVar)
        self.pref_dwim_archive = Settings.boundTkVar(self, 'img_dwim_archive', tk.BooleanVar)
        self.pref_dwim_advance = Settings.boundTkVar(self, 'img_dwim_advance', tk.BooleanVar)
        self.pref_dwim_savetags = Settings.boundTkVar(self, 'img_dwim_savetags', tk.BooleanVar)
        self.pref_dwim_only_one = Settings.boundTkVar(self, 'img_dwim_only_one', tk.BooleanVar)

        self.pref_autosave.trace_add('write', self.configure_visual)

        self.initwindow()
        self.bind_controls()


        self.after_idle(self.pick_images)

        self.mainloop()

    def initwindow(self):
        self.title("Image Search")
        self.geometry("1400x610")

        self.rowconfigure(0, weight=1)

        ccx = Increment()

        col = self.fac_image_list_frame(self)
        col.grid(column=ccx.inc(), row=0, sticky="ns")

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8, width=350)) as (col, cx, cy):
            col.grid(column=ccx.inc(), row=0, sticky="nsew")

            self.tag_editor_list = TagEditorList(col)
            self.tag_editor_list.grid(column=0, row=cy.inc(), sticky="nsew")
            col.rowconfigure(cy.value, weight=1)
            col.columnconfigure(0, weight=1, minsize=200)

            self.btn_save_tags = ttk.Button(col, text="Save Tags", command=self.save_tag_list)
            self.btn_save_tags.grid(column=0, row=cy.inc(), sticky="ew")

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

        with tkwrap(ttk.PanedWindow(self)) as (col):
            col.grid(column=ccx.inc(), row=0, rowspan=2, sticky="nsew")

            with tkwrap(grooveframe(col)) as row:
                row.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

                lab = ttk.Label(row, textvariable=self.textvar_info, anchor=tk.N, width=40, wraplength=250)
                lab.pack(anchor=tk.N, fill=tk.BOTH, expand=True)

            with tkwrap(grooveframe(col)) as row:
                row.pack(side=tk.TOP, fill=tk.X)

                for (var, label) in [
                    (self.pref_autosave, "Autosave Changes"),
                    (self.pref_dwim_archive, "DWIM: Archive"),
                    (self.pref_dwim_advance, "DWIM: Advance"),
                    (self.pref_dwim_savetags, "DWIM: Save tags"),
                    (self.pref_dwim_only_one, "DWIM: Only one"),
                ]:
                    ttk.Checkbutton(
                        row,
                        variable=var,
                        text=label
                    ).pack(anchor='n', fill='x')

            with tkwrapc(ttk.Frame(col, relief=tk.GROOVE, padding=4)) as (row, crx, cry):
                row.pack(side=tk.TOP, fill=tk.X)

                btn_refresh = ttk.Button(row, text="Refresh", command=self.refresh_current)
                btn_refresh.grid(column=crx.inc(), row=cry.inc(), sticky="ew")


    def bind_controls(self):
        entry: tk.Entry = self.tag_editor_list.entry_add

        self.tag_editor_list.bind("<<Modified>>", self.configure_visual)

        self.image_list.tree.configure(takefocus=False)

        entry.bind("<Right>", lambda e: entry.get() == "" and self.next_image())
        entry.bind("<Left>", lambda e: entry.get() == "" and self.prev_image())
        entry.bind("<Next>", lambda e: self.next_image())
        entry.bind("<Prior>", lambda e: self.prev_image())

        entry.bind("<Control-e>", self.toggle_keep)
        entry.bind("<Control-d>", self.toggle_delete)

        self.tag_editor_list.bind("<<DWIM>>", self.entry_dwim)
        self.tag_editor_list.pb = self.pb

        entry.focus()

    def entry_dwim(self, event=None):
        edited = False

        if self.pref_dwim_savetags.get() and not self.pref_autosave.get():
            if self.tag_editor_list.modified:
                self.save_tag_list()
                edited = True
                if self.pref_dwim_only_one.get():
                    return

        if self.pref_dwim_archive.get():
            if self.current_image and self.current_image['is_inbox'] and not self.current_image['is_deleted']:
                self.toggle_keep()
                edited = True
                if self.pref_dwim_only_one.get():
                    return

        if self.pref_dwim_advance.get():
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
            self.refresh_current()
        except TypeError as e:
            self.logger.exception(f"Couldn't apply tag list: {self.tag_editor_list.tag_list=}, {self.tag_editor_list.modified}")
            raise e


    def set_image(self, metadata: logic.FileMetadata):
        super().set_image(metadata)

        self.update_text_info()

        self.canvas.set_image(metadata)

        self.refreshing = True
        tag_list = logic.local_tags(metadata)
        self.tag_editor_list.setTagList(tag_list)

        self.tag_editor_list.modified = False
        self.refreshing = False

        self.configure_visual()

    def on_image_selected(self, event: tk.Event):
        super().on_image_selected(event)

        widget: ttk.Treeview = event.widget # type: ignore

        for neighbor_id in get_selection_neighbors(widget):
            self.canvas.preload_image(self.known_metadata[int(neighbor_id)])

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

    def configure_visual(self, *event):
        # Actually, just autosave
        if self.pref_autosave.get():
            self.btn_save_tags.configure(state=tk.DISABLED)

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