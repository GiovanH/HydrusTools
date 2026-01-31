
from contextlib import contextmanager

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Generator, Literal, NamedTuple, TypedDict
import tkinter.font as tkFont

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


