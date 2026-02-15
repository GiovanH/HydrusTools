import concurrent.futures
import logging
import pprint
import threading
import tkinter as tk
from tkinter import ttk

import hydrus_api
from PIL import ImageTk

from .. import logic
from ..logic import FileMetadata

from ..component.gui_util import (
    Increment,
    QueryHistory,
    SearchQueryEntry,
    TreeviewHeadings,
    pb_iter,
    tkwrap,
    tkwrapc,
)
from ..component.multicolumnlistbox import MultiColumnListbox
from ..component.toolwindow import ToolWindow
from ..settings import Settings




ISTH = TreeviewHeadings(
    {
        "tags": "Local Tags",
        "urls": "URLs",
        "notes": "Notes"
    }
)

class ImageListFrame(ttk.Frame):  # noqa: PLR0904
    helpstr = """"""
    def __init__(self, master: ToolWindow, toolmaster=None, *args_,  **kwargs) -> None:
        super().__init__(master, *args_, **kwargs)

        self.toolmaster: ToolWindow = toolmaster or master
        self.logger = self.toolmaster.logger
        self.setStatus = self.toolmaster.setStatus

        self.table: MultiColumnListbox

        self.image_size = (100, 100)

        self.image_cache = []
        self.known_metadata: dict[str, FileMetadata] = {}

        self.logger.info("Init widget")
        self.init_widget()

    def init_widget(self) -> None:
        self.columnconfigure(0, weight=1)

        # Right

        self.table = MultiColumnListbox(
            self,
            headers=ISTH.headings,
            imagesize=self.image_size
        )

        with tkwrap(self.table) as tree:
            tree.grid(column=0, row=1, sticky="nsew")
            self.rowconfigure(1, weight=1)


    def addItemFromMeta(self, metadata: FileMetadata, thumb=False):
        self.known_metadata[str(metadata['file_id'])] = metadata
        taglist = metadata['tags'][logic.local_tags_service_key]['display_tags'].get('0', [])
        self.table.insert_item({
            "id": metadata['file_id'],
            # "image": tkimg,
            "values": ISTH.values(
                tags='\n'.join(taglist),
                urls='\n'.join(metadata['known_urls']),
                notes=str(pprint.pformat(metadata['notes']))
            )
        })
        if thumb:
            self.addItemThumb(metadata)

    def delete_all(self):
        self.table.delete_all()

    def load_thumbnails(self, pb: ttk.Progressbar | dict = {'value': 0}):
        image_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        pb['value'] = 0

        lock = threading.Lock()

        thumb_tasks: list[FileMetadata] = [
            self.known_metadata[str(id)]
            for id in self.table.getAllIds()
        ]

        total = len(thumb_tasks)
        for i, metadata in enumerate(thumb_tasks):
            def task(i=i, metadata=metadata):
                self.addItemThumb(metadata)
                with lock:
                    pb['value'] = max(pb['value'], 100*(i+1)/total)

            image_pool.submit(task)

        image_pool.submit(self.logger.info, f"Loaded {total} thumbnails")
        self.logger.info(f"Queued {total} thumbnail jobs")

    def addItemThumb(self, metadata):
        if self.toolmaster.abort_threads:
            return

        item_id = metadata['file_id']

        thumb = logic.get_thumb_scaled(metadata['file_id'], *self.image_size)
        tkimg = ImageTk.PhotoImage(image=thumb, master=self)
        self.image_cache.append(tkimg)

        self.after('idle', lambda: self.table.tree.item(item_id, image=tkimg))


# class ImageSearchWindow(ToolWindow):  # noqa: PLR0904
#     helpstr = """TODO"""
#     def __init__(self, *args_, **kwargs) -> None:
#         super().__init__(*args_, **kwargs)

#         self.title("Image Search")
#         self.geometry("970x570")

#         self.columnconfigure(0, weight=1)
#         self.rowconfigure(0, weight=1)

#         self.results = []

#         frame_ra = ImageListFrame(self)
#         frame_ra.grid(column=0, row=0, sticky="nsew")

#         self.logger.info("Loop")
#         self.mainloop()

class ImagePickerWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """TODO"""
    def __init__(self, include_notes=False, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.include_notes = include_notes

        self.result: list[FileMetadata] | None = None
        self.textvar_query: tk.StringVar = Settings.boundTkVar(self, name='imagesearch_query')
        self.textvar_query_hist: tk.StringVar = Settings.boundTkVar(self, name='imagesearch_query_hist')

        self.initwindow()


    def initwindow(self):
        self.title("Image Search")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame_top, cx, _):
            frame_top.grid(column=0, row=counter_main_row.inc(), sticky="ew")

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=1)

            tk.Label(frame_top, text="Query:")\
                .grid(column=cx.value, row=0, sticky="w")

            self.entry_search = SearchQueryEntry(frame_top, textvariable=self.textvar_query, hist_store=self.textvar_query_hist)
            self.entry_search.grid(column=cx.value, row=1, sticky="ew")
            self.entry_search.bind("<Return>", self.startTaskCurry(self.doSearch, False))

            # cx.inc()
            # self.query_history = QueryHistory(
            #     frame_top, hist_store=self.textvar_query_hist
            # )
            # self.query_history.bind("<<HistorySelected>>", lambda e: self.textvar_query.set(e.widget.get()))
            # self.query_history.grid(column=cx.value, row=1, sticky="ew")

            cx.inc()
            btn_search = ttk.Button(frame_top, text="Search", command=self.startTaskCurry(self.doSearch, False))
            btn_search.grid(column=cx.value, row=1, sticky="ew")

        self.search_frame = ImageListFrame(self)
        self.search_frame.grid(column=0, row=counter_main_row.inc(), sticky="nsew")
        self.rowconfigure(counter_main_row.value, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as (frame_bottom, cx, cy):
            frame_bottom.grid(row=counter_main_row.inc(), sticky="ew")

            self.pb = ttk.Progressbar(frame_bottom, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=cx.inc(), row=0, sticky="ns")

            ttk.Label(frame_bottom, textvariable=self.textvar_status).grid(column=cx.inc(), row=0, sticky="nsew")
            frame_bottom.columnconfigure(cx.value, weight=1)

            btn_open = ttk.Button(frame_bottom, text="Pick all these images", command=self.confirm_all)
            btn_open.grid(column=cx.inc(), row=0, sticky="nse")

            btn_open = ttk.Button(frame_bottom, text="Pick selected images", command=self.confirm)
            btn_open.grid(column=cx.inc(), row=0, sticky="nse")

    def search_get_ids(self):
        try:
            tag_query = self.entry_search.get_query()
        except ValueError:
            self.setStatus("Empty search query!")
            return
        except RuntimeError as e:
            self.setStatus(e)
            return

        self.setStatus(f"Searching for query {tag_query!r}")
        self.search_frame.delete_all()

        try:
            resp = logic.client.search_files(
                tags=tag_query # type: ignore
            )
            matching_files = resp['file_ids']
        except hydrus_api.APIError as e:
            self.setStatus(str(e))
            return

        return matching_files

    def doSearch(self, event=None, load_thumbnails=True):
        matching_files = self.search_get_ids()
        if not matching_files:
            return

        self.entry_search.add_history(self.textvar_query.get())
        self.setStatus(f"Getting metadata for {len(matching_files)} files")

        for id_chunk in pb_iter(self.pb, [*logic.chunk(matching_files, 200)]):
            resp = logic.client.get_file_metadata(file_ids=id_chunk, include_notes=self.include_notes)

            def commit(resp=resp):
                for metadata in resp['metadata']:
                    # pprint.pprint(metadata)
                    self.search_frame.addItemFromMeta(metadata)

            self.after('idle', commit)

        if load_thumbnails:
            self.setStatus("Loading thumbnails")
            self.search_frame.load_thumbnails(self.pb)

    def confirm(self, event=None):
        ids = self.search_frame.table.getSelectionIDs()
        try:
            self.result = [
                self.search_frame.known_metadata[id] for id in ids
            ]
        except KeyError:
            # print(ids, self.search_frame.known_metadata.keys())
            raise
        self.logger.info(f"Returning result {len(self.result)=}")
        self.destroy()

    def confirm_all(self, event=None):
        if len(self.search_frame.table.getAllIds()) == 0:
            self.doSearch(load_thumbnails=False)
            self.update_idletasks()

        ids = self.search_frame.table.getAllIds()

        try:
            self.result = [
                self.search_frame.known_metadata[id] for id in ids
            ]
        except KeyError:
            # print(ids, self.search_frame.known_metadata.keys())
            raise
        self.logger.info(f"Returning result {len(self.result)=}")
        self.destroy()

    @classmethod
    def pick(cls):
        print("Starting new instance")
        instance = cls()
        print("Instance concluded, returning result")
        return instance.result

if __name__ == "__main__":
    logic.init_client()
    print("value:", ImagePickerWindow.pick())
