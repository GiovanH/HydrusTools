import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

import hydrus_api

from .tool.win_implicit_parents import ImplicitParentWindow
from .tool.win_tagrelationships import TagRelationshipsWindow

from . import logic
from .component.gui_util import tkwrapc
from .macro import macro_creatortags, macro_localchars, macro_matching_namespace, macro_pages
from .settings import HTSettings
from .tool.win_altsync import AltSyncWindow
from .tool.win_flatten import FlattenWindow
from .tool.win_regex import RegexSearchWindow
from .tool.win_tagsearch import TagSearchWindow

Settings = HTSettings()


MENU: dict[str, list[tuple[str, Callable | None]]] = {
    "Tag Management": [
        ("Tag Browser", TagSearchWindow),
        ("Tree Visualizer", None),
        ("Identify Reordered Character Names", macro_localchars.find_localchars),
    ],
    "Relationships": [
        # ("Relationship Browser", TagRelationshipsWindow),
        ("Flatten Siblings", FlattenWindow),
        ("Synchronize Alternates (WIP)", AltSyncWindow),
        ("Find implicit parents", ImplicitParentWindow),
        # ("Find implicit parents Macro", macro_implicit_parents.run),
        ("Detect tags' namespaced equivalents", macro_matching_namespace.run),
        ("Make Series from Character Parens", None),
        # We really want tag relationships for these...
        ("Parent characters to series", None),
        ("Detect Tag Siblings from Names", None),
        # ("Detect Tag Parents from Subsets", None),
    ],
    "Search": [
        ("Note Search", RegexSearchWindow),
    ],
    "Metadata Lookup": [
        ("Image Lookup", None),
        ("Import Downloader Tags In Local Repo", None),
        ("Extract Tags from Notes", None),
    ],
    "Filename Macros": [
        ("Extract known creators from filename note", macro_creatortags.find_creators),
        ("Extract page numbers from filename note", macro_pages.add_page_tags),
    ],
    "Unsorted": [
        # ("Tag Editor", None),
        ("Mail Rules", None),
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
        self.geometry("250x540")
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
