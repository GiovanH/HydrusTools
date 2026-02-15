from hydrustools.component.multicolumnlistbox import MultiColumnListbox

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
from ..component.multicolumnlistbox import MultiColumnListbox, TreeListItemDict
from ..component.toolwindow import ToolWindow
from ..settings import Settings


class HydrusImageTable(MultiColumnListbox):
    def __init__(
        self,
        master,
        toolmaster: None | ToolWindow = None,
        *args_,  **kwargs
    ) -> None:
        self.imagesize: tuple[int, int]
        super().__init__(master, *args_, **kwargs)

        self.toolmaster: ToolWindow = toolmaster or master
        self.logger = self.toolmaster.logger
        self.setStatus = self.toolmaster.setStatus


        self.image_cache = []

    # def addItemFromMeta(self, metadata: FileMetadata, thumb=False):
    #     self.known_metadata[str(metadata['file_id'])] = metadata
    #     taglist = metadata['tags'][logic.local_tags_service_key]['display_tags'].get('0', [])
    #     self.table.insert_item({
    #         "id": metadata['file_id'],
    #         # "image": tkimg,
    #         "values": ISTH.values(
    #             tags='\n'.join(taglist),
    #             urls='\n'.join(metadata['known_urls']),
    #             notes=str(pprint.pformat(metadata['notes']))
    #         )
    #     })
    #     if thumb:
    #         self.addItemThumb(metadata)

    def insert_item(self, item: TreeListItemDict) -> str: # type: ignore
        # item['values']['_hydrus_id']
        return super().insert_item(item)

    def load_thumbnails(self, pb: ttk.Progressbar | dict = {'value': 0}):
        image_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        pb['value'] = 0

        lock = threading.Lock()

        thumb_tasks: list[tuple] = [
            (tkid, self.tree.set(tkid, column=0))
            for tkid in
            self.tree.get_children()
        ]
        # print(self.getAllDicts(), thumb_tasks)

        total = len(thumb_tasks)
        for i, (tkid, file_id) in enumerate(thumb_tasks):
            # print(i, tkid, file_id)
            def task(i=i, file_id=file_id, tkid=tkid):
                self.addItemThumb(file_id=file_id, tkid=tkid)
                with lock:
                    pb['value'] = max(pb['value'], 100*(i+1)/total)

            image_pool.submit(task)

        image_pool.submit(self.logger.info, f"Loaded {total} thumbnails")  # TODO might not be last
        self.logger.info(f"Queued {total} thumbnail jobs")

    def addItemThumb(self, file_id, tkid):
        if self.toolmaster.abort_threads is True:
            self.logger.debug("Aborting thumbnail %s %s", file_id, tkid)
            return

        thumb = logic.get_thumb_scaled(file_id, *self.imagesize)
        tkimg = ImageTk.PhotoImage(image=thumb, master=self)
        self.image_cache.append(tkimg)

        self.logger.debug(f"Applying image {tkimg} to tkid {tkid}")
        self.after('idle', lambda: self.tree.item(tkid, image=tkimg))
