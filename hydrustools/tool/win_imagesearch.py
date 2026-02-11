from functools import lru_cache, partial
from io import BytesIO
import logging
import pprint
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk
from typing import TypedDict
from PIL import Image, ImageTk
import cv2
import hydrus_api
import numpy as np

import hydrus_api
import requests

from hydrustools import logic

from ..component.gui_util import Increment, TreeviewHeadings, tkwrap, tkwrapc
from ..component.multicolumnlistbox import MultiColumnListbox
from ..component.toolwindow import ToolWindow
from ..settings import HTSettings

logging.basicConfig(level=logging.INFO)


Settings = HTSettings()

ISTH = TreeviewHeadings(
    {
        "tags": "Local Tags",
        "urls": "URLs"
    }
)

@lru_cache(maxsize=None)
def photoimage(master, resp: requests.Response) -> ImageTk.PhotoImage:
    image = Image.open(BytesIO(resp.content))
    return ImageTk.PhotoImage(image=image, master=master)

class ImageSearchWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """Bulk search and edit tags.

Tag Query searches the tag list, regex refinment filters further.

AND/OR opens search page for all images with the selected tags.

"Map Siblings to Namespace" prompts for a namespace, then gives you an importable clipboard setting that will add the ideal sibling {namespace}:{tag} for each selected {tag}.

"Delete selected tag" removes all occurrences of the selected tags from all images.
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_query: tk.StringVar = Settings.boundTkVar(self, name='imagesearch_query')
        self.pb: ttk.Progressbar
        self.tree_tags: MultiColumnListbox

        self.image_cache = []

        self.initwindow()

        self.after(10, self.doSearch)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Tag Search")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame_top, cx, _):
            frame_top.grid(column=0, row=counter_main_row.inc(), sticky="ew", columnspan=2)

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=1)

            tk.Label(frame_top, text="Query:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Entry(frame_top, font=('Courier', 10), textvariable=self.textvar_query)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            btn_search = ttk.Button(frame_top, text="Search", command=self.startTaskCurry(self.doSearch))
            btn_search.grid(column=cx.value, row=1, sticky="ew")

        # Right
        counter_main_row.inc()
        self.tree_tags = MultiColumnListbox(self, headers=ISTH.headings)

        with tkwrap(self.tree_tags) as tree:
            tree.grid(column=0, row=counter_main_row.value, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as (frame_bottom, cx, cy):
            frame_bottom.grid(row=counter_main_row.inc(), columnspan=2, sticky="ew")

            self.pb = ttk.Progressbar(frame_bottom, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=cx.inc(), row=0, sticky="ns")

            ttk.Label(frame_bottom, textvariable=self.textvar_status).grid(column=cx.inc(), row=0, sticky="nsew")
            frame_bottom.columnconfigure(cx.value, weight=1)

            # with tkwrapc(ttk.Frame(frame_bottom)) as (frame, ccx, ccy):
            #     frame.grid(column=cx.inc(), row=0, sticky="nse")

            #     btn_search = ttk.Button(frame, text="AND search selected", command=self.openPageAnd)
            #     btn_search.grid(row=ccy.inc(), sticky="nsew")

            #     btn_search = ttk.Button(frame, text="OR search selected", command=self.openPageOr)
            #     btn_search.grid(row=ccy.inc(), sticky="nsew")

            # btn_search = ttk.Button(frame_bottom, text="Add Namespace", command=self.addNamespace)
            # btn_search.grid(column=cx.inc(), row=0, sticky="nse")

            # btn_search = ttk.Button(frame_bottom, text="Map to siblings with namespace", command=self.addNamespace)
            # # btn_search.config(state=tk.DISABLED)
            # btn_search.grid(column=cx.inc(), row=0, sticky="nse")

            # btn_search = ttk.Button(frame_bottom, text="Delete selected tag", command=self.deleteTags)
            # btn_search.grid(column=cx.inc(), row=0, sticky="nse")

    def doSearch(self, event=None):
        tag_query: str = self.textvar_query.get()
        if not tag_query:
            self.setStatus("Empty search query!")
            return

        self.setStatus(f"Searching for query {tag_query!r}")
        try:
            resp = logic.client.search_files(
                tags=[tag_query] # type: ignore
            )
            matching_files = resp['file_ids']
        except hydrus_api.APIError as e:
            self.setStatus(str(e))
            return

        self.setStatus(f"Getting metadata for {len(matching_files)} files")


        for id_chunk in logic.chunk(matching_files, 20):
            resp = logic.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

            for metadata in resp['metadata']:
                pprint.pprint(metadata)

                self.addItemFromMeta(metadata)
                # self.after(0, self.addItemFromMeta, metadata)

            self.setStatus(f"Aborting early")
            break

    def addItemFromMeta(self, metadata: dict):
        thumb_resp = logic.client.get_thumbnail(metadata['file_id'])
        thumb_resp.raise_for_status()
        tkimg = photoimage(self, thumb_resp)

        self.image_cache.append(tkimg)

        new_item = self.tree_tags.insert_item({
            "image": tkimg,
            "values": ISTH.values(
                tags=metadata['tags'][logic.local_tags_service_key]['display_tags'].get('0'),
                urls=len(metadata['known_urls'])
            )
        })
