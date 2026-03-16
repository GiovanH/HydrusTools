
import logging
import pprint
import threading
import tkinter as tk
from collections import defaultdict
from contextlib import contextmanager
from tkinter import messagebox
from typing import Any, Callable, Generator, Iterable

from hydrustools.settings import HTSettings, settings_section
from hydrustools.utils.util import timer

# Shared with gui.py
@settings_section(section="ToolsList")
class GuiSettings(HTSettings):
    gui_last: int = -1
    gui_test_list: list[str] = []


def recursive_widgets(w, key) -> Iterable[tk.Widget]:
    if key in 'state' in w.keys():
        yield w
    for w2 in w.winfo_children():
        yield from recursive_widgets(w2, key)


class ToolWindow(tk.Toplevel):
    label: str = ""
    helpstr: str = """Change this help string"""

    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_status = tk.StringVar(self, value="Ready")
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.abort_threads = False

        self.bind("<F1>", lambda *a: self.showHelp())

        self.bind("<Escape>", self.abort)

        self.locking_lock = threading.Lock()
        self._locked = 0
        self._lock_states = defaultdict(list)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def abort(self, event=None):
        self.abort_threads = True

    def on_closing(self):
        GuiSettings.gui_last = -1
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
        # pprint.pprint(self._lock_states)
        for w in recursive_widgets(self, 'state'):
            if not w.widgetName.endswith('label'):
                state = self._lock_states[w.winfo_name()].pop()
                w.configure(state=state) # type: ignore
        # pprint.pprint(self._lock_states)

    def disable(self):
        # pprint.pprint(self._lock_states)
        for w in recursive_widgets(self, 'state'):
            if not w.widgetName.endswith('label'):
                self._lock_states[w.winfo_name()].append(w['state'])
                w.configure(state=tk.DISABLED) # type: ignore
        # self.logger.info(self._lock_states)
        # pprint.pprint(self._lock_states)

    @contextmanager
    def lock(self) -> Generator[None, Any, None]:
        with self.locking_lock:
            self.logger.debug("Locking; %s += 1", self._locked)
            self._locked += 1
            if self._locked == 1:
                self.logger.debug("Locked, disabling")
                self.disable()
        try:
            yield
        finally:
            with self.locking_lock:
                self.logger.debug("Unlocking; %s -= 1", self._locked)
                self._locked -= 1
                if self._locked == 0:
                    self.logger.debug("Unlocked, enabling")
                    self.enable()

    def startTask(self, callback, lock=True) -> None:
        def task():
            with timer(repr(callback), logger=self.logger.info):
                if lock:
                    with self.lock():
                        callback()
                else:
                    callback()

        taskthread = threading.Thread(target=task, daemon=True)
        taskthread.start()

    def startTaskCurry(self, callback, lock=True) -> Callable[..., None]:
        return lambda *event: self.startTask(callback, lock=lock)
