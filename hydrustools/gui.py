import logging
import tkinter as tk
import traceback
import webbrowser
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable

import hydrus_api

from hydrustools.component.toolwindow import ToolWindow
from hydrustools.tool.win_image_extract_creator_from_notes import ExtractCreatorFromNotesWin

from . import htlogging, logic
from .component.gui_util import tkwrapc
from .macro import macro_localize_char_names, macro_matching_namespaced, macro_pages_from_note
from .settings import Settings
from .tool.win_image_inspector import ImageInspectorWin
from .tool.win_image_lookup import ImageMetadataLookupWin
from .tool.win_imrel_altsync import AlternatesSyncWin
from .tool.win_imsearch_regex import RegexNoteSearchWin
from .tool.win_tag_manager import TagManagerWin
from .tool.win_tagrel_flatten import SiblingFlattenWin
from .tool.win_tagrel_implicit_parents import ImplicitParentFinderWin
from .tool.win_tagrel_treebrowser import TagRelationshipsTreeWin

GH_HOME = 'https://github.com/GiovanH/HydrusTools'

htlogging.configure_logging()

def showDocFac(label: str, fn: Callable) -> None | Callable[..., None]:
    if not fn.__doc__:
        return None
    def showDoc(label=label, fn=fn):
        messagebox.showinfo(
            title=f"Help for {label}",
            message=fn.__doc__
        )
    return showDoc

@dataclass
class MenuEntry():
    label: str
    command: Callable | None = None
    showHelp: Callable | None = None
    is_tool: bool = False

    @classmethod
    def f(cls, *a):
        if len(a) == 1:
            (o,) = a
            if (isinstance(o, type) and issubclass(o, ToolWindow)):
                return cls(
                    label=o.label,
                    command=o,
                    showHelp=o.showHelp,
                    is_tool=True
                )

        if len(a) == 2:
            label, o = a
            if (isinstance(o, type) and issubclass(o, ToolWindow)):
                if o.label:
                    print("Extra label specified for", o, label, o.label)
                return cls(
                    label=label,
                    command=o,
                    showHelp=o.showHelp,
                    is_tool=True
                )
            elif callable(o):
                return cls(
                    label=label,
                    command=o,
                    showHelp=showDocFac(label, o)
                )
            elif o is None:
                return cls(
                    label=label,
                    command=o
                )
        raise NotImplementedError(a)


MENU: dict[str, list[MenuEntry]] = {
    "Tag Management": [
        MenuEntry.f(TagManagerWin),
        MenuEntry.f(ImageInspectorWin),
        MenuEntry.f("Tree Visualizer", None),
        MenuEntry.f(
            "Localize (Swapped) Character Names",
            macro_localize_char_names.find_localchars
        ),
    ],
    "Tag Relationships": [
        MenuEntry.f(SiblingFlattenWin),
        MenuEntry.f(ImplicitParentFinderWin),
        # ("Find implicit parents Macro", macro_implicit_parents.run),
        MenuEntry.f("Detect Tags' Namespaced Equivalents", macro_matching_namespaced.run),
        MenuEntry.f("Parent Series from Character Parens", None),
        # We really want tag relationships for these...
        # ("Detect Tag Siblings from Names", None),
        # ("Detect Tag Parents from Subsets", None),
    ],
    "Search": [
        MenuEntry.f(RegexNoteSearchWin),
    ],
    "Metadata Lookup": [
        MenuEntry.f(ImageMetadataLookupWin),
        MenuEntry.f(ExtractCreatorFromNotesWin),
        MenuEntry.f("Import Downloader Tags In Local Repo", None),
        MenuEntry.f("Extract Tags from Note Regex", None),
    ],
    "Filename Macros": [
        # ("Extract creators from filename note", macro_creators_from_note.start),
        MenuEntry.f("Extract page numbers from filename note", macro_pages_from_note.add_page_tags),
    ],
    "Unsorted and WIP": [
        # ("Tag Editor", None),
        MenuEntry.f(TagRelationshipsTreeWin),
        MenuEntry.f("Mail Rules", None),
        MenuEntry.f(AlternatesSyncWin),
    ],
    "About": [
        MenuEntry.f(
            "by GiovanH (GitHub)",
            lambda: webbrowser.open(GH_HOME)
        ),
    ],
}

class ToolsListWindow(tk.Tk):  # noqa: PLR0904
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)

        self.command_list: list[MenuEntry] = []
        self.initwindow()

        if Settings.gui_last != -1:
            try:
                entry = self.command_list[Settings.gui_last]
                # self.logger.info(f"{command}, {Settings.gui_last} {self.command_list[Settings.gui_last]=}")
                if entry.is_tool:
                    assert entry.command
                    self.iconify()
                    entry.command()
            except IndexError as e:
                self.logger.error(e)
                Settings.gui_last = -1
                pass

        self.mainloop()

    def initwindow(self) -> None:
        self.geometry("280x780")
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

                for entry in items:
                    self.command_list.append(entry)

                    def _launch(entry=entry):
                        if entry.is_tool:
                            assert entry.command
                            # self.logger.info(f"Setting last as {label}, {command}")
                            Settings.gui_last = self.command_list.index(entry)
                        if entry.command:
                            # taskthread = threading.Thread(target=command, daemon=True)
                            # taskthread.start()
                            entry.command()

                    btn = ttk.Button(frame_btns, text=entry.label, command=_launch)
                    cy.inc()

                    colspan = 1
                    if entry.showHelp:
                        btn_help = ttk.Button(frame_btns, text="?", command=entry.showHelp, width=2) # type: ignore
                        btn_help.grid(row=cy.value, column=1, pady=2)
                    else:
                        colspan = 2

                    btn.grid(row=cy.value, column=0, columnspan=colspan, sticky="ew", pady=2)

                    if entry.command is None:
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
