import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

import hydrus_api

from . import htlogging, logic
from .component.gui_util import tkwrapc
from .macro import macro_creators_from_note, macro_localize_char_names, macro_matching_namespaced, macro_pages_from_note
from .settings import Settings
from .tool.win_image_inspector import ImageInspectorWin
from .tool.win_image_lookup import ImageMetadataLookupWin
from .tool.win_imrel_altsync import AlternatesSyncWin
from .tool.win_imsearch_regex import RegexNoteSearchWin
from .tool.win_tag_manager import TagManagerWin
from .tool.win_tagrel_flatten import SiblingFlattenWin
from .tool.win_tagrel_implicit_parents import ImplicitParentFinderWin
from .tool.win_tagrel_treebrowser import TagRelationshipsTreeWin

htlogging.configure_logging()

MENU: dict[str, list[tuple[str, Callable | None]]] = {
    "Tag Management": [
        ("Tag Manager", TagManagerWin),
        ("Image Inspector", ImageInspectorWin),
        ("Tree Visualizer", None),
        ("Localize (Swapped) Character Names", macro_localize_char_names.find_localchars),
    ],
    "Tag Relationships": [
        ("Flatten Tag Siblings", SiblingFlattenWin),
        ("Find Implicit Parents", ImplicitParentFinderWin),
        # ("Find implicit parents Macro", macro_implicit_parents.run),
        ("Detect Tags' Namespaced Equivalents", macro_matching_namespaced.run),
        ("Parent Series from Character Parens", None),
        # We really want tag relationships for these...
        # ("Detect Tag Siblings from Names", None),
        # ("Detect Tag Parents from Subsets", None),
    ],
    "Search": [
        ("Note Search", RegexNoteSearchWin),
    ],
    "Metadata Lookup": [
        # ("Image Lookup", None),
        ("Import Downloader Tags In Local Repo", None),
        ("Extract Tags from Note Regex", None),
    ],
    "Filename Macros": [
        ("Extract creators from filename note", macro_creators_from_note.start),
        ("Extract page numbers from filename note", macro_pages_from_note.add_page_tags),
    ],
    "Unsorted and WIP": [
        # ("Tag Editor", None),
        ("Relationship Tree Browser", TagRelationshipsTreeWin),
        ("Image Metadata Lookup Test", ImageMetadataLookupWin),
        ("Mail Rules", None),
        ("Synchronize Alternate Meta (WIP)", AlternatesSyncWin),
        # ("Extract known creators from filename note", macro_creatortags.find_creators),
        # ("Extract page numbers from filename note", macro_pages.add_page_tags),
    ],
}

class ToolsListWindow(tk.Tk):  # noqa: PLR0904
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.command_list = []
        self.initwindow()

        if Settings.gui_last != -1:
            try:
                command = self.command_list[Settings.gui_last]
                self.logger.info(f"{command}, {Settings.gui_last} {self.command_list[Settings.gui_last]=}")
                if command and hasattr(command, "showHelp"):
                    self.iconify()
                    command()
            except IndexError as e:
                self.logger.error(e)
                Settings.gui_last = -1
                pass

        self.mainloop()

    def initwindow(self) -> None:
        self.geometry("250x780")
        self.title("Tools")

        self.columnconfigure(0, weight=1)
        # self.rowconfigure(1, weight=1)

        self.command_list = []

        with tkwrapc(ttk.Frame(self)) as (frame_btns, _, cy):
            # frame_btns.grid(row=1, ipadx=6, ipady=6, pady=6, padx=6, sticky="nsew")
            frame_btns.grid(row=1, padx=6, sticky="nsew")
            frame_btns.columnconfigure(0, weight=1)
            frame_btns.columnconfigure(1, weight=0, minsize=0)


            for group, items in MENU.items():
                lab = ttk.Label(frame_btns, text=group)
                lab.grid(row=cy.inc(), column=0, columnspan=2)

                for label, command in items:
                    self.command_list.append(command)

                    def _launch(label=label, command=command):
                        if command and hasattr(command, "showHelp"):
                            self.logger.info(f"Setting last as {label}, {command}")
                            Settings.gui_last = self.command_list.index(command)
                            command()
                        if command:
                            # taskthread = threading.Thread(target=command, daemon=True)
                            # taskthread.start()
                            command()

                    btn = ttk.Button(frame_btns, text=label, command=_launch)
                    cy.inc()

                    colspan = 1
                    if command and hasattr(command, "showHelp"):
                        btn_help = ttk.Button(frame_btns, text="?", command=command.showHelp, width=2) # type: ignore
                        btn_help.grid(row=cy.value, column=1, pady=2)
                    else:
                        colspan = 2

                    btn.grid(row=cy.value, column=0, columnspan=colspan, sticky="ew", pady=2)

                    if command is None:
                        btn.config(state=tk.DISABLED)


def main():

    try:
        logic.init_client()
    except hydrus_api.ConnectionError as e:
        messagebox.showerror(
            "Error connecting",
            message=f"{e}\n\nHydrus is probably not running!\n\nOtherwise, you can edit configuration in the INI file to change your API key or use a different API endpoint.",
        )
    except Exception as e:
        messagebox.showerror("Error connecting", message=f"{e}")
        raise

    ToolsListWindow()


if __name__ == "__main__":
    main()
