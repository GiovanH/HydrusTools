import concurrent.futures
import threading
from tkinter import ttk

from PIL import ImageTk

from .. import logic

from ..component.multicolumnlistbox import MultiColumnListbox, TreeListItemDict
from ..component.toolwindow import ToolWindow


class HydrusImageTable(MultiColumnListbox):
    file_id_key = 'file_id'

    def __init__(
        self,
        master,
        toolmaster: None | ToolWindow = None,
        *args_,  **kwargs
    ) -> None:
        super().__init__(master, *args_, **kwargs)

        self.toolmaster: ToolWindow = toolmaster or master
        self.logger = self.toolmaster.logger
        self.setStatus = self.toolmaster.setStatus

        self.image_cache = []

    def load_thumbnails(self, pb: ttk.Progressbar | dict = {'value': 0}):
        image_pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        pb['value'] = 0

        lock = threading.Lock()

        file_id_index = self.schema.columns.index(self.file_id_key)

        thumb_tasks: list[tuple] = [
            (tkid, self.tree.set(tkid, column=file_id_index))
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
        if self.schema.imagesize is None:
            self.logger.debug("Can't add thumbnail when schema has no imagesize")
            return

        thumb = logic.get_thumb_scaled(file_id, *self.schema.imagesize)
        tkimg = ImageTk.PhotoImage(image=thumb, master=self)
        self.image_cache.append(tkimg)

        self.logger.debug(f"Applying image {tkimg} to tkid {tkid}")

        def commititem(tkid=tkid, tkimg=tkimg):
            if not self.toolmaster.abort_threads:
                self.tree.item(tkid, image=tkimg)
        self.after('idle', commititem)
