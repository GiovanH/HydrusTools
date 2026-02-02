import logging
import tkinter as tk
from contextlib import contextmanager
from tkinter import ttk
from typing import Any, Generator, NamedTuple

import win32clipboard

logging.basicConfig(level=logging.INFO)

class Increment():
    def __init__(self):
        self.value = -1

    def inc(self):
        self.value += 1
        return self.value


class CoordFrame(NamedTuple):
    widget: tk.Widget
    counter_x: Increment
    counter_y: Increment


@contextmanager
def tkwrap(w: tk.Widget) -> Generator[tk.Widget, Any, None]:
    yield w


@contextmanager
def tkwrapc(w: tk.Widget) -> Generator[CoordFrame, Any, None]:
    yield CoordFrame(w, Increment(), Increment())


def flatList(lst):
    """Turn a (one-level) nested list into one list.
    >>> flatList([[1, 2], [3, 4]])
    [1, 2, 3, 4]
    """
    return [item for sublist in lst for item in sublist]


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    @property
    def container(self):
        return self.scrollable_frame


class TextCopyWindow(tk.Tk):
    helpstr = """Change this help string"""

    def __init__(self, body: str, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.body: str = body
        self.initwindow()
        self.focus()

        self.mainloop()

    def copy(self):
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(self.body) # type: ignore
        win32clipboard.CloseClipboard()

    def initwindow(self) -> None:
        self.title("Clipboard")
        self.geometry("400x250")

        text = tk.Text(self, padx=4, pady=4)
        text.insert(tk.END, self.body)
        # text.config(state=tk.DISABLED)
        text.grid(row=0, column=0, sticky="nsew")

        self.columnconfigure(index=0, weight=1)
        self.rowconfigure(index=0, weight=1)

        with tkwrapc(ttk.Frame(self, padding=4)) as (frame, cx, cy):
            frame.grid(row=1)

            btn = ttk.Button(frame, text="Copy", command=self.copy)
            btn.grid(row=0, column=cx.inc())

            btn = ttk.Button(frame, text="Close", command=self.destroy)
            btn.grid(row=0, column=cx.inc())

        self.bind("<Escape>", lambda *e: self.destroy())