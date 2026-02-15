from functools import lru_cache
from io import BytesIO
import tkinter as tk
from contextlib import contextmanager
from tkinter import ttk
from typing import Any, Generator, NamedTuple, Sequence, TypeVar
from PIL import Image, ImageTk

import requests
import win32clipboard

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


def get_selection_neighbors(widget: ttk.Treeview, prev=1, next=2) -> list[str]:
    """If an item is selected, return the id of the item's previous and next sibling."""
    selection = widget.selection()
    if not selection:
        return []
    item = selection[0]
    parent = widget.parent(item)
    siblings = list(widget.get_children(parent))
    try:
        idx = siblings.index(item)
    except ValueError:
        return []
    neighbors: list[str] = []
    for i in range(prev):
        idxo = idx - (i+1)
        if idxo >= 0:
            neighbors.append(siblings[idxo])
    for i in range(next):
        idxo = idx + 1+i
        if idxo < len(siblings):
            neighbors.append(siblings[idxo])
    return neighbors

def mod_selection(tree, prev, next):
    neighbors = get_selection_neighbors(tree, prev=prev, next=next)
    if not neighbors:
        return
    next_id = neighbors[0]
    tree.selection_set(next_id)
    tree.focus(next_id)
    tree.see(next_id)
    tree.event_generate("<<TreeviewSelect>>")


class TreeviewHeadings():
    """Maps column headings to row values for ttk.Treeview"""

    def __init__(self, headings: dict[str, str]):
        """Initialize with list of column headings"""
        self.headings = [*headings.values()]
        self._indices = {h: i for i, h in enumerate(headings.keys())}

    def values(self, **kwargs) -> list[str | None]:
        """Convert keyword args directly to row list"""
        row: list[str | None] = [None] * len(self.headings)
        for key, value in kwargs.items():
            if key in self._indices:
                row[self._indices[key]] = value
        return row

    def fromContext(self, **kwargs) -> list[str | None]:
        raise NotImplementedError


class NSVar(tk.StringVar):
    def get(self):
        """Return value of variable as string."""
        value = super().get()
        if value.endswith(":"):
            value = value.replace(":", "")
        return value



class QueryHistory(ttk.Combobox):
    def __init__(self, master, hist_store: tk.StringVar | None = None, history_length=10, *args, **kwargs):
        kwargs['width'] = 0
        super().__init__(master, *args, **kwargs)

        self.history_length = history_length

        if hist_store:
            self.hist_var: tk.StringVar = hist_store
            self.hist_list: list[str] = self.parse_hist(self.hist_var.get())
            self.populate_history()
        else:
            print("No history store!", self)

    #     self.bind("<<ComboboxSelected>>", self.reset)

    # def reset(self, event=None):
    #     self.event_generate("<<HistorySelected>>")
    #     self.after_idle(lambda *a: self.set(''))

    def parse_hist(self, hist_str: str) -> list[str]:
        return hist_str.split("|")

    def serialize_hist(self, hist: list[str]):
        return "|".join(hist)

    def populate_history(self):
        self.config(values=self.hist_list)

    def add_history(self, item: str):
        if item in self.hist_list:
            self.hist_list.remove(item)
        self.hist_list = [*self.hist_list[-self.history_length:], item]
        self.hist_var.set(self.serialize_hist(self.hist_list))
        self.populate_history()


class SearchQueryEntry(QueryHistory):
    def __init__(self, master: tk.Widget, textvariable: tk.StringVar, *args, **kwargs):
        self.textvar_query: tk.StringVar = textvariable

        kwargs['font'] = ('Courier', 10)
        kwargs['textvariable'] = self.textvar_query
        super().__init__(master, *args, **kwargs)

        self.bind("<<Paste>>", self.on_paste)

    def on_paste(self, event=None):
        """Handle paste events to replace newlines with ' AND '"""
        try:
            clipboard_text = self.clipboard_get()
            processed_text = self.load_query(clipboard_text)

            # Handle selection if exists
            try:
                sel_start = self.index(tk.SEL_FIRST)
                sel_end = self.index(tk.SEL_LAST)
                self.delete(sel_start, sel_end)
                insert_pos = sel_start
            except tk.TclError:
                # No selection, use cursor position
                insert_pos = self.index(tk.INSERT)

            # Insert processed text
            self.insert(insert_pos, processed_text)

            return "break"  # Prevent default paste behavior
        except tk.TclError:
            # Clipboard empty or error
            pass

    def load_query(self, value):
        return value.replace("\n", " AND ")

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