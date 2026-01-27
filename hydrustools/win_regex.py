import re
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from . import logic
from .gui_util import Increment, ToolWindow, tkwrap

from .settings import HTSettings
Settings = HTSettings()

class RegexSearchWindow(ToolWindow):
    helpstr = """Search the contents of notes.

Note title specifies the title of the note to search.
This will also try to match "incremented" titles caused by metadata merge, so "filename" also matches "filename (1)", etc.

Search pattern specifies the regular expression used. By default this has to match the start of the string, but the partial option will try to find the pattern anywhere in the note body.

Once the search is complete, results are sent to Hydrus in a notification. Click the button in Hydrus to open the page with search results.
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_notename = Settings.boundTkVar(self, 'note_notename')
        self.textvar_pattern = Settings.boundTkVar(self, 'note_pattern')
        self.boolvar_partial = Settings.boundTkVar(self, 'note_partial')
        # tk.BooleanVar(self, value=False)

        self.initwindow()
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Search Notes")
        self.geometry("450x160")

        self.columnconfigure(index=0, weight=1)
        self.rowconfigure(index=0, weight=1)
        main_row = Increment()

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as frame_form:
            frame_form.grid(column=0, row=main_row.inc(), sticky="nsew")
            frame_form.columnconfigure(index=1, weight=1)

            tk.Label(frame_form, text="Note title").grid(column=0, row=0, sticky="e")
            entry_search = ttk.Entry(frame_form, textvariable=self.textvar_notename)
            self.interactive_widgets.append(entry_search)
            entry_search.grid(column=1, row=0, sticky="ew")

            tk.Label(frame_form, text="Search pattern").grid(column=0, row=1, sticky="e")
            entry_search = ttk.Entry(frame_form, font=('Courier', 10), textvariable=self.textvar_pattern)
            self.interactive_widgets.append(entry_search)
            entry_search.grid(column=1, row=1, sticky="ew")

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as frame_row:
            frame_row.grid(column=0, row=main_row.inc(), sticky="nsew")
            frame_row.columnconfigure(index=0, weight=1)
            frame_row.columnconfigure(index=1, weight=1)

            tk.Label(frame_row, text="Match partial string").grid(column=0, row=0, sticky="e")
            check_partial = ttk.Checkbutton(frame_row, variable=self.boolvar_partial)
            self.interactive_widgets.append(check_partial)
            check_partial.grid(column=1, row=0, sticky="w")

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as frame_row:
            frame_row.grid(column=0, row=main_row.inc(), sticky="ew")
            frame_row.columnconfigure(index=0, weight=1)

            btn_search = ttk.Button(frame_row, text="Search", command=self.startSearch)
            btn_search.grid(column=0, row=0, sticky="ew")
            self.interactive_widgets.append(btn_search)

        with tkwrap(ttk.Frame(self, padding=0)) as frame_status:
            frame_status.grid(column=0, row=main_row.inc(), sticky="ew")
            frame_status.columnconfigure(index=0, weight=1)
            tk.Label(frame_status, textvariable=self.textvar_status).grid(column=0, row=1, sticky="e")

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

            # TODO: Option to configure " (n)" suffix
            max_n = 4
            tag_query: list[str] = [[
                *[f'system:has note with name "{notename}"'],
                *[f'system:has note with name "{notename} ({n})"' for n in range(1, max_n)]
            ]] # type: ignore
            print(tag_query)
            resp = logic.client.search_files(
                tags=tag_query
            )
            file_ids_with_note = resp['file_ids']

            self.setStatus(f"Found {len(file_ids_with_note)} files with notename {notename!r}...")

            matching_ids = []
            checked_file_count = 0
            start_time = time.time()

            try:
                for id_chunk in logic.chunk(file_ids_with_note, 100):
                    resp = logic.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

                    for metadata in resp['metadata']:
                        note_body = metadata['notes'].get(notename)
                        if matcher(pattern, note_body):
                            matching_ids.append(metadata['file_id'])
                        checked_file_count += 1

                    self.setStatus(f"Searched {checked_file_count} / {len(file_ids_with_note)}, matched {len(matching_ids)}...")
            except re.error as e:
                self.setStatus(str(e))
                return

            elapsed = time.time() - start_time
            logic.client.add_popup("Regex search complete", files_label=f"{notename}: {pattern!r}", file_ids=matching_ids)

            self.setStatus(f"Matched {len(matching_ids)} / {len(file_ids_with_note)} in {elapsed:.1f} secs, sent to Hydrus.")
