import functools
import io
from itertools import permutations
import pprint
import re
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

import numpy as np

import cv2
import hydrus_api

from .toolwindow import ToolWindow
from .tageditorlist import TagEditorList

from . import logic
from .gui_util import Increment, ScrollableFrame, flatList, tkwrap, tkwrapc

@functools.lru_cache
def alternatesOfHash(file_hash):
    file_relationships = logic.client.get_file_relationships(
        hashes=[file_hash]
    )['file_relationships']
    return file_relationships[file_hash][str(hydrus_api.DuplicateStatus.ALTERNATES.value)]

class AltSyncWindow(ToolWindow):
    helpstr = """Interactively synchronize metadata between alternate images.

An automatic search will gather image sets whose tags don't all already match each other in the column on the left.

Select a set to preview the images. This will load a combined set of tags into the central editor interface, which you can modify before merging if desired.

Clicking merge will add the specified tags to all images in the set.
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        # self.textvar_notename = tk.StringVar(self, value="filename")
        # self.textvar_pattern = tk.StringVar(self, value="^Doorspit, lust.+")
        # self.boolvar_partial = tk.BooleanVar(self, value=False)
        self.file_ids: list[str] = []
        self.tag_cache: dict[str, list] = {}

        self.selected_group_hashes: list[str] = []
        # self.merged_tag_list = []
        self.last_selected_item = None

        self.initwindow()

        self.startTask(self.loadIdsWithAlternates, lock=False)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Synchronize Alternates")
        self.geometry("650x450")

        counter_main_row = Increment()

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame, cx, cy):
            frame.grid(column=0, row=counter_main_row.inc(), sticky="ew", columnspan=3)

        counter_main_row.inc()
        self.rowconfigure(index=counter_main_row.value, weight=1)
        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame, cx, cy):
            frame.grid(column=0, row=counter_main_row.value, sticky="ns")

            tk.Label(frame, text="Alternates").grid(column=0, row=cy.inc(), sticky="sw")

            self.listbox_ids = tk.Listbox(frame)
            self.listbox_ids.grid(column=0, row=cy.inc(), sticky="ns")
            frame.rowconfigure(index=cy.value, weight=1)

            self.listbox_ids.bind('<<ListboxSelect>>', self.loadSelectedId)

            vsb = ttk.Scrollbar(frame, orient="vertical", command=self.listbox_ids.yview)
            vsb.grid(column=1, row=cy.value, sticky='ns')
            self.listbox_ids.configure(yscrollcommand=vsb.set)

        self.tag_editor_list = TagEditorList(self)
        self.tag_editor_list.grid(column=1, row=counter_main_row.value, sticky="nsew")
        self.columnconfigure(index=1, weight=3)

        # with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame, cx, cy):

        #     tk.Label(frame, text="Merged tags").grid(column=0, row=cy.inc(), sticky="ew")
        #     self.listbox_tag_merge = tk.Listbox(frame)
        #     self.listbox_tag_merge.grid(column=0, row=cy.inc(), sticky="nsew")
        #     frame.rowconfigure(index=cy.value, weight=1)
        #     frame.columnconfigure(index=0, weight=1)

        #     def removeTag(event: tk.Event):
        #         widget = event.widget
        #         assert isinstance(widget, tk.Listbox)
        #         selected_index = widget.curselection()
        #         selected_item = widget.get(selected_index[0])
        #         widget.delete(selected_index)

        #     self.listbox_tag_merge.bind('<<ListboxSelect>>', removeTag)

        #     def addEnteredTag(event: tk.Event):
        #         widget: tk.Entry = event.widget # type: ignore
        #         assert isinstance(widget, tk.Entry)

        #         value = widget.get()
        #         if value not in self.merged_tag_list:
        #             self.merged_tag_list.append(value)
        #             self.listbox_tag_merge.insert(tk.END, value)

        #         widget.delete(0, tk.END)

        #     tk.Label(frame, text="Add tags").grid(column=0, row=cy.inc(), sticky="ew")
        #     entry_add = ttk.Entry(frame)
        #     self.interactive_widgets.append(entry_add)
        #     entry_add.bind("<Return>", addEnteredTag)
        #     entry_add.grid(column=0, row=cy.inc(), sticky="ew")

        #     # self.listbox_tag_merge.bind('<<ListboxSelect>>', self.loadSelectedId)

        #     vsb = ttk.Scrollbar(frame, orient="vertical", command=self.listbox_tag_merge.yview)
        #     vsb.grid(column=1, row=cy.value, sticky='ns')
        #     self.listbox_tag_merge.configure(yscrollcommand=vsb.set)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE)) as (frame, cx, cy):
            # TODO Convert this to a scrollable text area
        # with tkwrapc(ScrollableFrame(self, relief=tk.GROOVE, width=300)) as (frame, cx, cy):
        #     assert isinstance(frame, ScrollableFrame)
            frame.grid(column=2, row=counter_main_row.value, sticky="nsew")
            self.columnconfigure(index=2, weight=1)
            # self.inspector_frame = frame.container
            self.inspector_frame = frame

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame, cx, cy):
            frame.grid(column=0, row=counter_main_row.inc(), sticky="ew", columnspan=3)
            tk.Label(frame, textvariable=self.textvar_status).grid(column=0, row=0, sticky="sw")
            frame.columnconfigure(0, weight=1)

            btn_merge = ttk.Button(frame, text="Merge Selected Tags", command=self.mergeSelectedTags)
            btn_merge.grid(column=1, row=0, sticky="ew")
            self.interactive_widgets.append(btn_merge)

            # btn_merge = ttk.Button(frame, text="Merge Relationships", command=self.mergeRelationships)
            # btn_merge.grid(column=2, row=0, sticky="ew")
            # self.interactive_widgets.append(btn_merge)


    def loadIdsWithAlternates(self, event=None):
        all_file_hashes = logic.client.search_files(
            tags=["system:num file relationships > 0 alternates"],
            return_hashes=True
        )['hashes']

        # pprint.pprint(all_file_hashes)

        self.listbox_ids.delete(0, self.listbox_ids.size())

        self.setStatus("Filtering to non-matching alternate groups...")
        for hash in all_file_hashes:
            if hash not in self.file_ids and not self.allAlternateTagsMatch(hash):
                self.file_ids.append(hash)
                self.listbox_ids.insert(tk.END, hash)

        # self.updateFileListbox()

        self.setStatus(f"Found {len(self.file_ids)} files with alternates.")

    def getTagsOfHashes(self, hash_list):
        if not all(h in self.tag_cache for h in hash_list):
            metadata = logic.client.get_file_metadata(
                hashes=hash_list
            )['metadata']
            # pprint.pprint(metadata)

            for file_metadata in metadata:
                try:
                    tags = file_metadata['tags'][logic.local_tags_service_key]['display_tags'].get(str(hydrus_api.TagStatus.CURRENT.value), [])
                    # pprint.pprint(tags)
                    self.tag_cache[file_metadata['hash']] = [t for t in tags if not t.startswith("source:")]
                except:
                    pprint.pprint(file_metadata)
                    raise

        return {
            hash: self.tag_cache[hash]
            for hash in hash_list
        }

    def allAlternateTagsMatch(self, file_hash):
        alternate_hashes = alternatesOfHash(file_hash)
        # pprint.pprint(alternate_hashes)

        all_hashes = [file_hash, *alternate_hashes]
        tag_map = self.getTagsOfHashes(all_hashes)
        for h1, h2 in permutations(tag_map.keys(), r=2):
            if set(tag_map[h1]) != set(tag_map[h2]):
                return False
        return True

    def loadSelectedId(self, event=None):
        selected_index = self.listbox_ids.curselection()
        if selected_index:
            selected_item = self.listbox_ids.get(selected_index[0])
        elif self.last_selected_item:
            selected_item = self.last_selected_item
        else:
            self.setStatus("No alternate selected, nothing to load.")
            return

        self.last_selected_item = selected_item

        # metadata_pre = logic.client.get_file_metadata(
        #     hashes=[selected_item],
        #     only_return_basic_information=True
        # )['metadata']
        file_hash = selected_item
        # pprint.pprint(file_hash)

        alternate_hashes = alternatesOfHash(file_hash)
        self.selected_group_hashes = [file_hash, *alternate_hashes]
        tag_map = self.getTagsOfHashes(self.selected_group_hashes)

        # cv2.waitKey(0)

        new_tag_list = sorted(set(flatList(tag_map.values())))
        self.tag_editor_list.setTagList(new_tag_list)

        with tkwrapc(self.inspector_frame) as (frame, cx, cy):
            for widget in frame.winfo_children():
                widget.destroy()

            for i, hash in enumerate(self.selected_group_hashes):
                # cx.inc()
                # frame.columnconfigure(index=cx.value, weight=1)
                tk.Label(frame, text=f"Image {i}")\
                    .grid(row=cy.inc(), column=0, sticky="w")
                tk.Label(frame, text='\n'.join(tag_map[hash]))\
                    .grid(row=cy.inc(), column=1, sticky="w")

        self.previewSelectedImages()

        # cv2.destroyAllWindows()
    def previewSelectedImages(self):
        self.setStatus(f"Loading preview of {len(self.selected_group_hashes)} files")
        for i, file_hash in enumerate(self.selected_group_hashes):
            resp = logic.client.get_render(
                hash_=file_hash,
                width=400, height=400
            )
            resp.raise_for_status()

            image_array = np.frombuffer(resp.content, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            cv2.imshow(f'Image {i}', image)
            # cv2.resizeWindow(f'Image {i}', 400, 400)

                # tk.Label(frame, text=hash)\
                #     .grid(column=0, row=cx.inc(), sticky="sw")

    def mergeSelectedTags(self, event=None):
        self.setStatus("Adding new tags...")
        logic.client.add_tags(
            hashes=self.selected_group_hashes,
            service_keys_to_tags={
                logic.local_tags_service_key: self.tag_editor_list.tag_list,
            }
        )
        self.setStatus("Pruning removed tags...")

        tag_map = self.getTagsOfHashes(self.selected_group_hashes)
        all_tags = set(flatList(tag_map.values()))

        self.logger.info("%s, %s", all_tags, set(self.tag_editor_list.tag_list))

        removed_tags = set(all_tags).difference(set(self.tag_editor_list.tag_list))

        self.setStatus(f"Pruning removed tags... {removed_tags}")
        if removed_tags:
            logic.client.add_tags(
                hashes=self.selected_group_hashes,
                service_keys_to_actions_to_tags={
                    logic.local_tags_service_key: {
                        hydrus_api.TagAction.DELETE: [*removed_tags]
                    }
                }
            )

        self.setStatus("Merged tags!")

        for h in self.selected_group_hashes:
            if h in self.tag_cache:
                del self.tag_cache[h]
        self.loadSelectedId()

    def mergeRelationships(self, event=None):
        pass