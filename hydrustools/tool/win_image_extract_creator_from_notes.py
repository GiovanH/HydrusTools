import re
import tkinter as tk
from tkinter import ttk

from hydrustools.utils import querylang
import hydrustools.utils.util

from ..component.tag_adder_window import TagAction, TagAdderFrame
from ..component.toolwindow import ToolWindow
from ..settings import HTSettings, settings_section
from ..utils import hydrus
from ..utils.gui_util import SearchQueryEntry, pb_iter, tkwrapc

@settings_section(section="ExtractCreator")
class Settings(HTSettings):
    extractcreatornote_search: str = ""
    extractcreatornote_search_hl: list[str] = []
    extractcreatornote_notename: str = "filename"
    extractcreatornote_min_count: int = 2


def all_creator_names(min_count=2):
    creator_tags = hydrus.client.search_tags(
        search="creator:*",
        tag_service_key=hydrus.local_tags_service_key,
        tag_display_type="display"
    )['tags']  # type: ignore
    creator_names = [
        tag['value'].replace('creator:', '').replace(' (artist)', '')
        for tag in creator_tags
        if tag['count'] >= min_count
    ]
    return creator_names



class ExtractCreatorFromNotesWin(ToolWindow):  # noqa: PLR0904
    label = "Extract Creator Tags from Notes"
    helpstr = """
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.var_search: tk.StringVar = Settings.boundTkVar(self, 'extractcreatornote_search')
        # self.var_search_hist: tk.StringVar = Settings.boundTkVar(self, 'extractcreatornote_search_hist')
        self.var_notename: tk.StringVar = Settings.boundTkVar(self, 'extractcreatornote_notename')
        self.var_min_count: tk.IntVar = Settings.boundTkVar(self, 'extractcreatornote_min_count', tk.IntVar)

        self.abort_threads = False

        self.initwindow()
        self.bind("<Delete>", self.frame_ta.deleteSelected)


        self.startTask(self.doSearch, lock=False)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Extract Creator from Notes")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=4)) as (frame, cx, cy):
            frame.grid(column=0, row=0, sticky="ew")

            cx.inc()
            tk.Label(frame, text="Image filter:")\
                .grid(column=cx.value, row=0, sticky="w")

            self.entry_search = SearchQueryEntry(frame, textvariable=self.var_search, hist_store=(Settings, 'extractcreatornote_search_hl'))
            self.entry_search.grid(column=cx.value, row=1, sticky="ew")
            frame.columnconfigure(index=cx.value, weight=1)
            self.entry_search.bind("<Return>", self.startTaskCurry(self.doSearch, lock=False))

            cx.inc()
            tk.Label(frame, text="Note name:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_notename = ttk.Entry(frame, textvariable=self.var_notename)
            entry_notename.grid(column=cx.value, row=1, sticky="ew")
            entry_notename.bind("<Return>", self.startTaskCurry(self.doSearch, lock=False))

            cx.inc()
            tk.Label(frame, text="Minimum creator count:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_count = ttk.Spinbox(frame, textvariable=self.var_min_count, from_=1, to=500)
            entry_count.grid(column=cx.value, row=1, sticky="ew")
            entry_count.bind("<Return>", self.startTaskCurry(self.doSearch, lock=False))

            cx.inc()
            frame.columnconfigure(cx.value, weight=1)

            cx.inc()
            btn_search = ttk.Button(frame, text="Search", command=self.startTaskCurry(self.doSearch, lock=False))
            btn_search.grid(column=cx.value, row=1, sticky="ew")

        self.frame_ta = TagAdderFrame(self, pack_buttons=False)
        self.frame_ta.grid(column=0, row=1, sticky="nsew")

        with tkwrapc(ttk.Frame(self)) as (frame, cx, cy):
            frame.grid(column=0, row=2, sticky="ew")

            self.pb = ttk.Progressbar(frame, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=cx.inc(), row=0, sticky="ns")

            ttk.Label(frame, textvariable=self.textvar_status).grid(column=cx.inc(), row=0, sticky="nsew")
            frame.columnconfigure(index=cx.value, weight=1)

            btn = self.frame_ta.btn_open_sel(frame)
            btn.grid(column=cx.inc(), row=0, sticky="nse")

            btn = self.frame_ta.btn_apply_sel(frame)
            btn.grid(column=cx.inc(), row=0, sticky="nse")

            btn = self.frame_ta.btn_apply_all(frame)
            btn.grid(column=cx.inc(), row=0, sticky="nse")

    def all_creator_patterns(self, creator_names) -> list[tuple[str, re.Pattern]]:
        creator_patterns: list[tuple[str, re.Pattern]] = []

        for name in creator_names:
            try:
                if len(name) > 4 and name not in {'anonymous', 'unknown', 'anon', 'unknown artist'}:
                    creator_patterns.append((name, re.compile(rf'(^|\b|[_+-]){re.escape(name)}(\b|[_+-])')))
            except re.error:
                self.logger.error(f"Couldn't create search pattern for name {name=!r}")
                continue

        return creator_patterns

    def doSearch(self):
        self.abort_threads = False
        self.pb['value'] = 0

        self.pb['value'] += 25
        min_count = self.var_min_count.get()
        self.setStatus(f"Getting all creators with >= {min_count} instances")
        creator_names = all_creator_names(min_count=min_count)
        creator_patterns: list[tuple[str, re.Pattern]] = self.all_creator_patterns(creator_names)

        notename = self.var_notename.get()

        tag_query: querylang.Query = self.entry_search.get_query()

        self.entry_search.add_history(self.var_search.get())

        tag_query.append(hydrus.has_note(notename))
        tag_query.append("-creator:*")

        self.frame_ta.delete_all()

        self.pb['value'] += 25
        self.setStatus(f"Searching for files with note {notename!r} and no creator...")
        file_ids_with_note = hydrus.client.search_files(
            tags=tag_query
        )['file_ids']

        self.setStatus(f"Found {len(file_ids_with_note)} files matching {tag_query!r}...")

        self.setStatus(f"Searching for any of {len(creator_names)} creator tags in {len(file_ids_with_note)} filenames")

        for id_chunk in pb_iter(self.pb, [*hydrustools.utils.util.chunk(file_ids_with_note, 200)]):
            if self.abort_threads:
                self.setStatus("Aborted")
                return

            resp = hydrus.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

            for metadata in resp['metadata']:
                note_body = metadata['notes'].get(notename)
                for (name, pattern) in creator_patterns:
                    match = pattern.search(note_body)
                    if not match:
                        continue

                    new_tag = f"creator:{name}"

                    action = TagAction(metadata['file_id'], note_body, [new_tag])

                    # self.setStatus(f"Added {action}")

                    self.frame_ta.add_item(action)
                    # return

            # if len(tag_actions) > 2:
            #     break

        self.winfo_toplevel().after(10, self.frame_ta.tree_tags.resize_cols)
        self.setStatus("Done!")

if __name__ == "__main__":
    hydrus.init_client()
    ExtractCreatorFromNotesWin()
