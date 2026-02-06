import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tqdm.tk import tqdm as tqdmtk

import hydrus_api

from .macro import macro_creatortags

from . import logic
from .component.gui_util import TextCopyWindow, tkwrapc
from .macro import macro_pages
from .settings import HTSettings
from .tool.win_altsync import AltSyncWindow
from .tool.win_flatten import FlattenWindow
from .tool.win_regex import RegexSearchWindow
from .tool.win_tagsearch import TagSearchWindow

Settings = HTSettings()


class ToolsWindow(tk.Tk):  # noqa: PLR0904
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.initwindow()

        self.mainloop()

    def initwindow(self) -> None:
        self.geometry("250x540")
        self.title("Tools")

        self.columnconfigure(0, weight=1)
        # self.rowconfigure(1, weight=1)

        with tkwrapc(ttk.Frame(self)) as (frame_btns, _, cy):
            # frame_btns.grid(row=1, ipadx=6, ipady=6, pady=6, padx=6, sticky="nsew")
            frame_btns.grid(row=1, padx=6, sticky="nsew")
            frame_btns.columnconfigure(0, weight=1)
            frame_btns.columnconfigure(1, weight=0, minsize=0)

            command_list = []

            for label, command in [
                ("Flatten Siblings", FlattenWindow),
                ("Note Search", RegexSearchWindow),
                ("Synchronize Alternates", AltSyncWindow),
                ("Tag Browser", TagSearchWindow),
                ("Tag Editor", None),
                ("Artist Lookup", None),
                ("Tree Visualizer", None),
                ("Import Downloader Tags In Local Repo", None),
                ("Extract Tags from Notes", None),
                # We really want tag relationships for these...
                ("Parent characters to series", None),
                ("Identify Reordered Character Names", None),
                ("Make Series from Character Parens", None),
                ("Detect Tag Siblings from Names", None),
                ("Detect Tag Parents from Subsets", None),
                ("Mail Rules", None),
                # ("Extract known creators from filename note", macro_creatortags.find_creators),
                # ("Extract page numbers from filename note", macro_pages.add_page_tags),
            ]:
                command_list.append(command)

                def _launch(label=label, command=command):
                    if command and hasattr(command, "showHelp"):
                        self.logger.info(f"Setting last as {label}, {command}")
                        Settings.gui_last = command_list.index(command)
                    if command:
                        command()

                btn = ttk.Button(frame_btns, text=label, command=_launch)
                btn.grid(row=cy.inc(), column=0, sticky="ew", pady=2)

                if hasattr(command, "showHelp"):
                    btn_help = ttk.Button(frame_btns, text="?", command=command.showHelp, width=2)
                    btn_help.grid(row=cy.value, column=1, pady=2)

                if command is None:
                    btn.config(state=tk.DISABLED)

            if Settings.gui_last != -1:
                try:
                    command = command_list[Settings.gui_last]
                    if command and hasattr(command, "showHelp"):
                        self.iconify()
                        command()
                except IndexError as e:
                    self.logger.error(e)
                    Settings.gui_last = -1
                    pass

        with tkwrapc(ttk.Frame(self)) as (frame_macros, _, cy):
            frame_macros.grid(row=2, padx=6, sticky="nsew")
            frame_macros.columnconfigure(0, weight=1)

            for label, command in [
                ("Extract known creators from filename note", macro_creatortags.find_creators),
                ("Extract page numbers from filename note", macro_pages.add_page_tags),
            ]:
                def runThread(command=command):
                    taskthread = threading.Thread(target=command, daemon=True)
                    taskthread.start()

                btn = ttk.Button(frame_macros, text=label, command=runThread)
                btn.grid(row=cy.inc(), column=0, sticky="ew", pady=2)

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

    # TextCopyWindow("Hello\nWorld")
    # RegexSearchWindow()
    # AltSyncWindow()
    ToolsWindow()
    # FlattenWindow()


if __name__ == "__main__":
    main()
