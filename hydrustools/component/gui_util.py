from functools import lru_cache
from io import BytesIO
import logging
import tkinter as tk
from contextlib import contextmanager
from tkinter import ttk
from typing import Any, Generator, NamedTuple, Sequence, TypeVar
from typing import TypedDict, Generic, TypeVar, Unpack
from PIL import Image, ImageTk

import requests
import win32clipboard

from ..settings import Settings

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


V = TypeVar("V")

def pb_iter(pb: ttk.Progressbar, seq: Sequence[V]) -> Generator[V, Any, None]:
    pb['value'] = 0
    total = len(seq)
    for i, item in enumerate(seq):
        yield item
        pb['value'] = 100*i/total
    pb['value'] = 0

@lru_cache(maxsize=None)
def resp_to_photoimage(master: tk.Widget, resp: requests.Response) -> ImageTk.PhotoImage:
    image = Image.open(BytesIO(resp.content))
    return ImageTk.PhotoImage(image=image, master=master)

class TreeviewHeadings():
    """Maps column headings to row values for ttk.Treeview"""

    def __init__(self, headings: dict[str, str]):
        """Initialize with list of column headings"""
        self.headings = [*headings.values()]
        self._indices = {h: i for i, h in enumerate(headings.keys())}

    def values(self, **kwargs):
        """Convert keyword args directly to row list"""
        row = [None] * len(self.headings)
        for key, value in kwargs.items():
            if key in self._indices:
                row[self._indices[key]] = value
        return row


class NSVar(tk.StringVar):
    def get(self):
        """Return value of variable as string."""
        value = super().get()
        if value.endswith(":"):
            value = value.replace(":", "")
        return value


class SearchQueryEntry(ttk.Entry):
    def __init__(self, master: tk.Widget, textvariable: tk.StringVar, *args, **kwargs):
        self.textvar_query: tk.StringVar = textvariable

        kwargs['font'] = ('Courier', 10)
        kwargs['textvariable'] = self.textvar_query
        super().__init__(master, *args, **kwargs)

    def get_query(self) -> list[str]:
        tag_query = self.textvar_query.get()
        if not tag_query:
            raise ValueError("Empty search query")
        return tag_query.split(' AND ')


class RegexEntry(ttk.Entry):
    def __init__(self, container, *args, **kwargs):
        kwargs['font'] = ('Courier', 10)
        super().__init__(container, *args, **kwargs)


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