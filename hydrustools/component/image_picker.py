import pprint
import tkinter as tk
from collections import OrderedDict
from tkinter import ttk
from typing import ClassVar

import hydrus_api

from hydrustools.component.HydrusImageTable import HydrusImageTable
from hydrustools.component.multicolumnlistbox import TreeListItemDict, TreeviewSchema

from ..component.toolwindow import ToolWindow
from ..settings import HTSettings, settings_section
from ..utils import hydrus
from ..utils.gui_util import (
    Increment,
    SearchQueryEntry,
    pb_iter,
    tkwrap,
    tkwrapc,
)
from ..utils.hydrus import FileMetadata


@settings_section(section="ImagePicker")
class Settings(HTSettings):
    imagesearch_query: str = ""
    imagesearch_query_hl: list[str] = []
    imagesearch_alts: bool = True


class ImageFileSchema(TreeviewSchema[FileMetadata]):
    headers: ClassVar[OrderedDict[str, str | None]] = OrderedDict([
        ('file_id', None),
        ('tag_list', 'Local Tags'),
        ('urls', 'URLs'),
        ('notes', 'Notes'),
    ])
    imagesize = (100, 100)

    @staticmethod
    def to_tree_item(item: FileMetadata) -> TreeListItemDict:
        taglist = hydrus.local_tags(item)
        return {
            "id": item['file_id'],
            "values": [
                item['file_id'],
                '\n'.join(taglist),
                '\n'.join(item['known_urls']),
                str(pprint.pformat(item['notes']))
            ]
        }


class ImageListFrame(ttk.Frame):
    helpstr = """"""
    def __init__(self, master: ToolWindow, toolmaster=None, *args_,  **kwargs) -> None:
        super().__init__(master, *args_, **kwargs)

        self.toolmaster: ToolWindow = toolmaster or master
        self.logger = self.toolmaster.logger
        self.setStatus = self.toolmaster.setStatus

        self.table: HydrusImageTable

        self.image_size = (100, 100)

        self.image_cache = []

        self.init_widget()

    def init_widget(self) -> None:
        self.columnconfigure(0, weight=1)

        # Right

        self.table = HydrusImageTable(
            self,
            toolmaster=self.toolmaster,
            schema=ImageFileSchema
        )

        with tkwrap(self.table) as tree:
            tree.grid(column=0, row=1, sticky="nsew")
            self.rowconfigure(1, weight=1)

    def delete_all(self):
        self.table.delete_all()


# class ImageSearchWindow(ToolWindow):
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

class ImagePickerWindow(ToolWindow):
    helpstr = """TODO"""
    def __init__(self, include_notes=False, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.include_notes = include_notes

        self.known_metadata: dict[int, FileMetadata] = {}

        self.result: list[FileMetadata] | None = None
        self.textvar_query: tk.StringVar = Settings.boundTkVar(self, name='imagesearch_query')
        self.boolvar_alts: tk.BooleanVar = Settings.boundTkVar(self, 'imagesearch_alts', tk.BooleanVar)

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

            self.entry_search = SearchQueryEntry(frame_top, textvariable=self.textvar_query, hist_store=(Settings, 'imagesearch_query_hl'))
            self.entry_search.grid(column=cx.value, row=1, sticky="ew")
            self.entry_search.bind("<Return>", self.startTaskCurry(self.doSearch, False))

            # cx.inc()
            # self.query_history = QueryHistory(
            #     frame_top, hist_store=self.textvar_query_hist
            # )
            # self.query_history.bind("<<HistorySelected>>", lambda e: self.textvar_query.set(e.widget.get()))
            # self.query_history.grid(column=cx.value, row=1, sticky="ew")

            cx.inc()
            tk.Label(frame_top, text="Add all related")\
                .grid(column=cx.value, row=0, sticky="w")

            check_alts = ttk.Checkbutton(frame_top, variable=self.boolvar_alts)
            check_alts.grid(column=cx.value, row=1, sticky="ew")

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

    def search_get_ids(self) -> list[int] | None:
        try:
            tag_query = self.entry_search.get_query()
        except ValueError:
            self.setStatus("Empty search query!")
            return
        except RuntimeError as e:
            self.setStatus(e)
            return

        self.pb['value'] = 10
        self.setStatus(f"Searching for query {tag_query!r}")
        self.search_frame.delete_all()

        try:
            resp = hydrus.client.search_files(
                tags=tag_query,
                tag_service_key=hydrus.local_tags_service_key
            )
            matching_files: list[int] = resp['file_ids']
        except hydrus_api.APIError as e:
            self.setStatus(str(e))
            return

        if self.boolvar_alts.get():
            self.pb['value'] = 90
            self.setStatus("Bundling in relationships...")
            matching_files = hydrus.addAltsToList(matching_files)

        self.pb['value'] = 0
        return matching_files

    def doSearch(self, event=None, load_thumbnails=True) -> None:
        matching_files = self.search_get_ids()
        if not matching_files:
            return

        self.abort_threads = False

        self.entry_search.add_history(self.textvar_query.get())
        self.setStatus(f"Getting metadata for {len(matching_files)} files")

        for id_chunk in pb_iter(self.pb, [*hydrus.chunk(matching_files, 200)]):
            resp = hydrus.client.get_file_metadata(file_ids=id_chunk, include_notes=self.include_notes)

            def commit(resp=resp) -> None:
                for metadata in resp['metadata']:
                    # pprint.pprint(metadata)
                    file_id: int = metadata['file_id']
                    self.known_metadata[file_id] = metadata
                    self.search_frame.table.insert_item(ImageFileSchema.to_tree_item(metadata))

            self.after('idle', commit)

        if load_thumbnails:
            self.setStatus("Loading thumbnails")
            self.search_frame.table.load_thumbnails(self.pb)

    def confirm(self, event=None) -> None:
        ids = self.search_frame.table.getSelectionIDs()
        try:
            self.result = [
                self.known_metadata[int(id)] for id in ids
            ]
        except KeyError:
            # print(ids, self.known_metadata.keys())
            raise
        self.logger.info(f"Returning result {len(self.result)=}")
        self.destroy()

    def confirm_all(self, event=None) -> None:
        if len(self.search_frame.table.getAllIds()) == 0:
            self.doSearch(load_thumbnails=False)
            self.update_idletasks()

        ids = self.search_frame.table.getAllIds()

        try:
            self.result = [
                self.known_metadata[int(id)] for id in ids
            ]
        except KeyError:
            # print(ids, self.known_metadata.keys())
            raise
        self.logger.info(f"Returning result {len(self.result)=}")
        self.destroy()

    @classmethod
    def pick(cls) -> list[FileMetadata] | None:
        print("Starting new instance")
        instance = cls()
        print("Instance concluded, returning result")
        return instance.result

if __name__ == "__main__":
    hydrus.init_client()
    print("value:", ImagePickerWindow.pick())
