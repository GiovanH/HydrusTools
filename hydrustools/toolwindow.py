
from contextlib import contextmanager

import logging
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Generator

from hydrustools.settings import HTSettings

Settings = HTSettings()

def recursive_widgets(w, key):
    if key in 'state' in w.keys():
        yield w
    for w2 in w.winfo_children():
        yield from recursive_widgets(w2, key)


class ToolWindow(tk.Tk):
    helpstr = """Change this help string"""

    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_status = tk.StringVar(self, value="Ready")
        self.logger = logging.getLogger(self.__class__.__name__)

        self.bind("<F1>", lambda *a: self.showHelp())

        self._locked = 0
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        Settings.gui_last = -1
        self.destroy()

    def setStatus(self, val):
        self.logger.info(val)
        self.textvar_status.set(val)

    @classmethod
    def showHelp(cls):
        messagebox.showinfo(
            title=f"Help for {cls.__name__}",
            message=cls.helpstr
        )

    def enable(self):
        for w in recursive_widgets(self, 'state'):
            w.configure(state=tk.NORMAL) # type: ignore

    def disable(self):
        for w in recursive_widgets(self, 'state'):
            w.configure(state=tk.DISABLED) # type: ignore

    @contextmanager
    def lock(self) -> Generator[None, Any, None]:
        self._locked += 1
        self.disable()
        try:
            yield
        finally:
            self._locked -= 1
            if self._locked == 0:
                self.enable()

    def startTask(self, callback, lock=True) -> None:
        def task():
            if lock:
                with self.lock():
                    callback()
            else:
                callback()

        threading.Thread(target=task, daemon=True).start()

    def startTaskCurry(self, callback) -> Callable[..., None]:
        return lambda *a: self.startTask(callback)
