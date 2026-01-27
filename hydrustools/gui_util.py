
from contextlib import contextmanager

import logging
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from typing import Any, Generator, NamedTuple

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
def tkwrap(w: tk.Widget):
    yield w

@contextmanager
def tkwrapc(w: tk.Widget):
    yield CoordFrame(w, Increment(), Increment())


def flatList(lst):
    """Turn a (one-level) nested list into one list.
    >>> flatList([[1, 2], [3, 4]])
    [1, 2, 3, 4]
    """
    return [item for sublist in lst for item in sublist]

class ToolWindow(tk.Tk):
    helpstr = """Change this help string"""

    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_status = tk.StringVar(self, value="Ready")
        self.logger = logging.getLogger(self.__class__.__name__)
        self.interactive_widgets: list[tk.Widget] = []

        self._locked = 0

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
        for w in self.interactive_widgets:
            w.configure(state=tk.NORMAL) # type: ignore

    def disable(self):
        for w in self.interactive_widgets:
            try:
                w.configure(state=tk.DISABLED) # type: ignore
            except:
                print(w)
                raise

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

    def startTask(self, callback, lock=True):
        def task():
            if lock:
                with self.lock():
                    callback()
            else:
                callback()

        threading.Thread(target=task, daemon=True).start()

    def startTaskCurry(self, callback):
        return lambda *a: self.startTask(callback)

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


class TagEditorList(ttk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.tag_list = []

        self.initwindow()

    def validate(self):
        box_list = self.listbox_taglist.get(0, self.listbox_taglist.size())
        try:
            for (listval, boxval) in zip(self.tag_list, box_list):
                assert listval == boxval
        except:
            print(self.tag_list, box_list)
            print(list(zip(self.tag_list, box_list)))
            raise

    def setTagList(self, tag_list):
        self.listbox_taglist.delete(0, self.listbox_taglist.size())

        self.tag_list = tag_list

        for tag in self.tag_list:
            self.listbox_taglist.insert(tk.END, tag)

        self.validate()

    def addTag(self, new_tag):
        if new_tag not in self.tag_list:
            self.tag_list.append(new_tag)
            self.listbox_taglist.insert(tk.END, new_tag)

        self.validate()

    def removeTag(self, target_tag):
        index = self.tag_list.index(target_tag)
        self.listbox_taglist.delete(index)
        self.tag_list.pop(index)

        self.validate()

    def removeSelectedTags(self, event: tk.Event):
        widget = event.widget
        assert isinstance(widget, tk.Listbox)

        for selected_index in widget.curselection()[::-1]:
            self.removeTag(widget.get(selected_index))

        self.validate()

    def addTagFromEntry(self, event: tk.Event):
        widget: tk.Entry = event.widget # type: ignore
        assert isinstance(widget, tk.Entry)

        value = widget.get()
        self.addTag(value)

        widget.delete(0, tk.END)

        self.validate()

    def initwindow(self) -> None:
        with tkwrapc(self) as (frame, cx, cy):
            # tk.Label(frame, text="Merged tags").grid(column=0, row=cy.inc(), sticky="ew")
            self.listbox_taglist = tk.Listbox(frame, selectmode=tk.EXTENDED)
            self.listbox_taglist.grid(column=0, row=cy.inc(), sticky="nsew")
            frame.rowconfigure(index=cy.value, weight=1)
            frame.columnconfigure(index=0, weight=1)

            self.listbox_taglist.bind('<Delete>', self.removeSelectedTags)

            vsb = ttk.Scrollbar(frame, orient="vertical", command=self.listbox_taglist.yview)
            vsb.grid(column=1, row=cy.value, sticky='ns')
            self.listbox_taglist.configure(yscrollcommand=vsb.set)

            tk.Label(frame, text="Add tags").grid(column=0, row=cy.inc(), sticky="ew")
            entry_add = ttk.Entry(frame)
            # self.interactive_widgets.append(entry_add)
            entry_add.bind("<Return>", self.addTagFromEntry)
            entry_add.grid(column=0, row=cy.inc(), sticky="ew")

            # self.listbox_taglist.bind('<<ListboxSelect>>', self.loadSelectedId)

            self.listbox_suggestion = tk.Listbox(frame)
            self.listbox_suggestion.grid(column=0, row=cy.inc(), sticky="nsew")
            frame.rowconfigure(index=cy.value, minsize=2, weight=0)