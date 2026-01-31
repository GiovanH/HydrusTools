import logging
import tkinter as tk
from tkinter import messagebox, ttk

import hydrus_api

from .win_altsync import AltSyncWindow

from .gui_util import tkwrapc

from . import logic
from .win_flatten import FlattenWindow
from .win_regex import RegexSearchWindow

from .settings import HTSettings
Settings = HTSettings()

class ToolsWindow(tk.Tk):  # noqa: PLR0904
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.interactive_widgets = []
        self.initwindow()

        self.mainloop()

    def enable(self):
        for w in self.interactive_widgets:
            w.config(state=tk.ACTIVE)

    def disable(self):
        for w in self.interactive_widgets:
            try:
                w.config(state=tk.DISABLED)
            except:
                print(w)
                raise

    def initwindow(self) -> None:
        self.geometry("250x480")
        self.title("Tools")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        with tkwrapc(ttk.Frame(self)) as (frame_btns, _, cy):
            frame_btns.grid(row=1, ipadx=6, ipady=6, pady=6, padx=6, sticky="nsew")
            frame_btns.columnconfigure(0, weight=1)
            frame_btns.columnconfigure(1, weight=0, minsize=0)

            command_list = []

            for label, command in [
                ("Flatten Siblings", FlattenWindow),
                ("Note Search", RegexSearchWindow),
                ("Synchronize Alternates", AltSyncWindow),
                ("Tag Editor", None),
                ("Artist Lookup", None),
                ("Tree Visualizer", None),
                ("Parent characters to series", None),
                ("Tag Deleter", None),
                ("Tag Search", None),
                ("Import Downloader Tags In Local Repo", None),
                ("Extract Tags from Notes", None),
                ("Mail Rules", None),
                ("Identify Reordered Character Names", None),
                ("Make Series from Character Parens", None),
                ("Detect Tag Siblings from Names", None),
                ("Detect Tag Parents from Subsets", None),
            ]:
                command_list.append(command)

                def _launch(label=label, command=command):
                    self.logger.info(f"Setting last as {label}, {command}")
                    if command:
                        Settings.gui_last = command_list.index(command)
                        command()

                btn = ttk.Button(frame_btns, text=label, command=_launch)
                btn.grid(row=cy.inc(), column=0, sticky="ew", pady=2)

                if hasattr(command, 'showHelp'):
                    btn_help = ttk.Button(frame_btns, text="?", command=command.showHelp, width=2)
                    btn_help.grid(row=cy.value, column=1, pady=2)
                    self.interactive_widgets.append(btn)

                if command is None:
                    btn.config(state=tk.DISABLED)

            if Settings.gui_last != -1:
                command = command_list[Settings.gui_last]
                self.logger.info(command_list)
                if command:
                    self.iconify()
                    command()

def main():
    try:
        logic.init_client()
    except hydrus_api.ConnectionError as e:
        messagebox.showerror("Error connecting", message=f"{e}\n\nHydrus is probably not running!\n\nOtherwise, you can edit configuration in the INI file to change your API key or use a different API endpoint.")
    except Exception as e:
        messagebox.showerror("Error connecting", message=f"{e}")
        raise

    # RegexSearchWindow()
    # AltSyncWindow()
    ToolsWindow()
    # FlattenWindow()

if __name__ == "__main__":
    main()
