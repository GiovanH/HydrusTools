import re
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

# import PyTaskbar

import hydrus_api

from ..component.toolwindow import ToolWindow

from .. import logic
from ..component.gui_util import Increment, tkwrap, tkwrapc

from ..settings import HTSettings
Settings = HTSettings()

def has_note(notename: str, max_n: int = 4) -> list[str]:
    return [
        *[f'system:has note with name "{notename}"'],
        *[f'system:has note with name "{notename} ({n})"' for n in range(1, max_n)]
    ]

class RegexSearchWindow(ToolWindow):
    helpstr = """Search the contents of notes.

Note title specifies the title of the note to search.
This will also try to match "incremented" titles caused by metadata merge, so "filename" also matches "filename (1)", etc.

Search pattern specifies the regular expression used. By default this has to match the start of the string, but the partial option will try to find the pattern anywhere in the note body.

Once the search is complete, results are sent to Hydrus in a notification. Click the button in Hydrus to open the page with search results.
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_prequery = Settings.boundTkVar(self, 'note_prequery')
        self.textvar_notename = Settings.boundTkVar(self, 'note_notename')
        self.textvar_pattern = Settings.boundTkVar(self, 'note_pattern')
        self.boolvar_partial = Settings.boundTkVar(self, 'note_partial', tk.BooleanVar)
        # tk.BooleanVar(self, value=False)

        self.initwindow()
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Search Notes")
        self.geometry("450x200")

        self.columnconfigure(index=0, weight=1)
        self.rowconfigure(index=0, weight=1)
        main_row = Increment()

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame_form, cx, cy):
            frame_form.grid(column=0, row=main_row.inc(), sticky="nsew")
            frame_form.columnconfigure(index=1, weight=1)

            tk.Label(frame_form, text="Search query").grid(column=0, row=cy.inc(), sticky="e")
            entry_search = ttk.Entry(frame_form, textvariable=self.textvar_prequery)
            entry_search.grid(column=1, row=cy.value, sticky="ew")

            tk.Label(frame_form, text="Note title").grid(column=0, row=cy.inc(), sticky="e")
            entry_search = ttk.Entry(frame_form, textvariable=self.textvar_notename)
            entry_search.grid(column=1, row=cy.value, sticky="ew")

            tk.Label(frame_form, text="Search pattern").grid(column=0, row=cy.inc(), sticky="e")
            entry_search = ttk.Entry(frame_form, font=('Courier', 10), textvariable=self.textvar_pattern)
            entry_search.grid(column=1, row=cy.value, sticky="ew")

        with tkwrap(ttk.Frame(self, padding=8)) as frame_row:
            frame_row.grid(column=0, row=main_row.inc(), sticky="nsew")
            frame_row.columnconfigure(index=0, weight=1)
            frame_row.columnconfigure(index=1, weight=1)

            tk.Label(frame_row, text="Match partial string").grid(column=0, row=0, sticky="e")
            check_partial = ttk.Checkbutton(frame_row, variable=self.boolvar_partial)
            check_partial.grid(column=1, row=0, sticky="w")

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as frame_row:
            frame_row.grid(column=0, row=main_row.inc(), sticky="ew")
            frame_row.columnconfigure(index=0, weight=1)

            btn_search = ttk.Button(frame_row, text="Search", command=self.startSearch)
            btn_search.grid(column=0, row=0, sticky="ew")

        with tkwrap(ttk.Frame(self, padding=0)) as frame_status:
            frame_status.grid(column=0, row=main_row.inc(), sticky="ew")
            self.pb = ttk.Progressbar(frame_status, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=1, row=0, sticky="ns")

            tk.Label(frame_status, textvariable=self.textvar_status).grid(column=0, row=0, sticky="e")
            frame_status.columnconfigure(index=0, weight=1)

    def startSearch(self, event=None):
        threading.Thread(target=self.doSearch, daemon=True).start()

    def doSearch(self, event=None):
        notename: str = self.textvar_notename.get()
        pattern: str = self.textvar_pattern.get()

        # TODO: Verify: Option to swap this with re.search
        matcher: Callable[..., Any] = re.match # re.search
        if self.boolvar_partial.get():
            matcher = re.search

        with self.lock():
            self.setStatus("Searching")
            # self.pb.start()
            self.pb['value'] = 0
            # progress = PyTaskbar.Progress()
            # progress.init()
            # progress.setState('loading')

            tag_query: list[str | list[str]] = [] # type: ignore

            # TODO: Option to configure " (n)" suffix
            tag_query.append(has_note(notename))

            if self.textvar_prequery.get():
                tag_query.append(self.textvar_prequery.get())

            self.setStatus(f"Searching for query {tag_query!r}")
            try:
                resp = logic.client.search_files(
                    tags=tag_query # type: ignore
                )
                file_ids_with_note = resp['file_ids']
            except hydrus_api.APIError as e:
                self.setStatus(str(e))
                return

            self.setStatus(f"Found {len(file_ids_with_note)} files with notename {notename!r}...")

            matching_ids = []
            checked_file_count = 0
            start_time = time.time()

            try:
                for id_chunk in logic.chunk(file_ids_with_note, 1000):
                    resp = logic.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

                    for metadata in resp['metadata']:
                        note_body = metadata['notes'].get(notename)
                        if matcher(pattern, note_body):
                            matching_ids.append(metadata['file_id'])
                        checked_file_count += 1


                    self.pb['value'] = 100*checked_file_count/len(file_ids_with_note)
                    # progress.setProgress(self.pb['value'])
                    self.setStatus(f"Searched {checked_file_count} / {len(file_ids_with_note)}, matched {len(matching_ids)}...")

                    if self.abort_threads: return
            except re.error as e:
                self.setStatus(str(e))
                return

            elapsed = time.time() - start_time
            logic.client.add_popup("Regex search complete", files_label=f"{notename}: {pattern!r}", file_ids=matching_ids)

            # self.pb.stop()
            # progress.setState('done')
            self.setStatus(f"Matched {len(matching_ids)} / {len(file_ids_with_note)} in {elapsed:.1f} secs, sent to Hydrus.")
