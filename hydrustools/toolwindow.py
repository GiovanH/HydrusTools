
from collections import defaultdict
from contextlib import contextmanager

import logging
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Generator, Iterable

from hydrustools.settings import HTSettings

Settings = HTSettings()

def recursive_widgets(w, key) -> Iterable[tk.Widget]:
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
        self.abort_threads = False

        self.bind("<F1>", lambda *a: self.showHelp())

        self._locked = 0
        self._lock_states = defaultdict(list)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        Settings.gui_last = -1
        self.abort_threads = True
        self.destroy()

    def setStatus(self, val):
        self.logger.info(val)

        max_old_lines = 2
        line = str(val)
        lines = self.textvar_status.get().split('\n')
        self.textvar_status.set('\n'.join([*lines[-max_old_lines:], line]))

    @classmethod
    def showHelp(cls):
        messagebox.showinfo(
            title=f"Help for {cls.__name__}",
            message=cls.helpstr
        )

    def enable(self):
        for w in recursive_widgets(self, 'state'):
            if not w.widgetName.endswith('label'):
                state = self._lock_states[w.winfo_name].pop()
                w.configure(state=state) # type: ignore

    def disable(self):
        for w in recursive_widgets(self, 'state'):
            if not w.widgetName.endswith('label'):
                self._lock_states[w.winfo_name].append(w['state'])
                w.configure(state=tk.DISABLED) # type: ignore
        # self.logger.info(self._lock_states)

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

        taskthread = threading.Thread(target=task, daemon=True)
        taskthread.start()

    def startTaskCurry(self, callback) -> Callable[..., None]:
        return lambda *a: self.startTask(callback)
