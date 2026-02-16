
from dataclasses import dataclass
import functools
import itertools
import logging
import re
import threading
import tkinter as tk
from tkinter import TclError, ttk
from typing import Any, Callable, Optional, Sequence

from hydrustools import htlogging, logic

from .gui_util import tkwrapc

# TODO: Better fuzzy searching
# TODO: Use - in entry to remove tags



@dataclass
class MatchResults:
    all: list[str]
    resolved: Optional[str]
    unique: bool

@functools.lru_cache()
def _matchSegments(q: str, query_split) -> list[str]:
    return [
        s for s in
        re.split(query_split, q)
        if s
    ]

@functools.lru_cache()
def _segmentMatches(collection: Sequence[str], query_split=r'[\\ /_:()-]'):
    grouped_segments = [
        (item, _matchSegments(item, query_split))
        for item in collection
    ]

    def lenSegmentsKey(is_):
        _item, item_segs = is_
        return len(item_segs)

    grouped_segments.sort(key=lenSegmentsKey)
    return grouped_segments

@functools.lru_cache()
def getMatches(query, collection: Sequence[str], query_split=r'[\\ /_:(-]', fuzzy=False, max_matches=64) -> MatchResults:
    """
    >>> getMatches("dav ja", collection)
    MatchResults(all=[], resolved=None, unique=False)
    >>> getMatches("ri j", collection, fuzzy=True)
    MatchResults(all=['vris john'], resolved='vris john', unique=True)
    >>> getMatches("jo", collection)
    MatchResults(all=['john', 'john rose'], resolved='john', unique=False)

    >>> getMatches("john", collection).resolved
    'john'
    >>> getMatches("john", collection).all
    ['john', 'john rose']

    >>> getMatches("-john", collection).resolved
    'vris john'
    >>> getMatches("-rose", collection).resolved
    'john rose'

    >>> getMatches("jo ro", collection).resolved
    'john rose'
    """
    matches = []

    query_segs: list[str] = _matchSegments(query, query_split)
    offsetize = True or bool(re.match(query_split, query))

    # Construct list of (item, segs) tuples sorted by the length of segments
    grouped_item_segs: list[tuple[Any, list[str]]] = _segmentMatches(collection, query_split)

    def addSegmentMatches(match_fn: Callable[[str, str], bool]):
        """Adds matches based on match_fn(theirs, ours): segmentMatches[True, False]"""
        for item, item_segs in grouped_item_segs:
            if item in matches:
                continue
            for offset in range(1 + len(item_segs) - len(query_segs)) if offsetize else [0]:
                # zipped = [*zip(item_segs, ['']*offset + query_segs)]
                zipped = [*itertools.zip_longest(
                    item_segs,
                    ([''] * offset) + query_segs,
                    fillvalue=''
                )]
                passes_test = all(match_fn(theirs, ours) for (theirs, ours) in zipped)
                # print(item, list(zipped), offset, offsetize, passes_test)
                if passes_test:
                    print(item, item_segs, zipped)
                    matches.append(item)
                    # break
            if len(matches) > max_matches:
                break

    addSegmentMatches(lambda theirs, ours: theirs.startswith(ours))

    if len(matches) == 0 and fuzzy:
        addSegmentMatches(lambda theirs, ours: (ours in theirs))

    best = None
    if len(matches) > 0:
        best = matches[0]

    return MatchResults(resolved=best, all=matches, unique=(len(matches) == 1))

class ListboxNavigator:
    def __init__(self, listbox: tk.Listbox):
        self.listbox = listbox
        self.current_index = 0

    def set(self, index):
        self.current_index = index
        self._update_selection()

    def clamp(self):
        if self.current_index > self.listbox.size() - 1:
            self.current_index = self.listbox.size() - 1
            self._update_selection()

    def move_up(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._update_selection()
        self.clamp()

    def move_down(self):
        if self.current_index < self.listbox.size() - 1:
            self.current_index += 1
            self._update_selection()
        self.clamp()

    def _update_selection(self):
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(self.current_index)
        self.listbox.see(self.current_index)

class TagEditorList(ttk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.tag_list = []
        self.modified = False

        self.all_tags: Sequence[str] = []
        self.last_query = ""
        self.last_tag: str | None = None

        self.aggressive = tk.BooleanVar(value=True)

        self.initwindow()

        self.suggestion_nav = ListboxNavigator(self.listbox_suggestion)

        self.bind_controls()

        threading.Thread(target=self.load_suggestions, daemon=True).start()


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

            tk.Label(frame, text="Add tags").grid(column=0, row=cy.inc(), columnspan=2, sticky="ew")

            self.entry_add = tk.Entry(
                frame,
                highlightthickness=2,
            )
            self.entry_add.grid(column=0, row=cy.inc(), columnspan=2, sticky="ew")

            # self.listbox_taglist.bind('<<ListboxSelect>>', self.loadSelectedId)

            self.listbox_suggestion = tk.Listbox(frame)
            self.listbox_suggestion.grid(column=0, row=cy.inc(), columnspan=2, sticky="nsew")
            frame.rowconfigure(index=cy.value, minsize=2, weight=0)

    def bind_controls(self):
        self.entry_add.bind("<Return>", self.entry_dwim)
        self.entry_add.bind("<Tab>", self.entry_complete)
        self.entry_add.bind("<Escape>", lambda e: self.listbox_suggestion.selection_clear(0, tk.END))
        self.entry_add.bind("<KeyRelease>", self.show_suggestions)

        self.entry_add.bind('<Up>', lambda e: self.suggestion_nav.move_up())
        self.entry_add.bind('<Down>', lambda e: self.suggestion_nav.move_down())
        self.entry_add.bind('<F5>', self.load_suggestions)

        self.entry_add.bind("<Control-period>", self.try_repeat)

    def try_repeat(self, event=None):
        if self.last_tag:
            self.addTag(self.last_tag)

    def validate(self):
        box_list = self.listbox_taglist.get(0, self.listbox_taglist.size())
        try:
            for (listval, boxval) in zip(self.tag_list, box_list):
                assert listval == boxval
        except:
            print(self.tag_list, box_list)
            print(list(zip(self.tag_list, box_list)))
            raise

    def setTagList(self, tag_list: list[str]):
        self.listbox_taglist.delete(0, self.listbox_taglist.size())

        # self.tag_list = tag_list
        self.tag_list.clear()

        for tag in logic.sort_tags(tag_list):
            self.addTag(tag)
            # self.listbox_taglist.insert(tk.END, tag)

        self.validate()

    def addTag(self, new_tag: str):
        if new_tag not in self.tag_list:
            self.tag_list.append(new_tag)
            self.listbox_taglist.insert(tk.END, new_tag)
            self.listbox_taglist.itemconfig(tk.END,
                foreground=logic.get_tag_color(new_tag),
            )
            self.modified = True
            self.event_generate("<<Modified>>")

        # print(self.listbox_taglist.itemconfig(len(self.tag_list)))

        self.validate()

    def removeTag(self, target_tag: str):
        index = self.tag_list.index(target_tag)
        self.listbox_taglist.delete(index)
        self.tag_list.pop(index)
        self.modified = True

        self.event_generate("<<Modified>>")
        self.validate()

    def removeSelectedTags(self, event: tk.Event):
        widget = event.widget
        assert isinstance(widget, tk.Listbox)

        for selected_index in widget.curselection()[::-1]:
            self.removeTag(widget.get(selected_index))

        self.validate()

    def entry_complete(self, event: tk.Event):
        try:
            selected = self.listbox_suggestion.selection_get()
        except TclError:
            selected = False
        if selected:
            self.entry_add.delete(0, tk.END)
            self.entry_add.insert(0, selected)

            self.after_idle(self.entry_add.focus)

    def entry_dwim(self, event: tk.Event):
        widget: tk.Entry = event.widget # type: ignore
        assert isinstance(widget, tk.Entry)

        try:
            selected_suggestion = self.listbox_suggestion.selection_get()
        except TclError:
            selected_suggestion = False
        if selected_suggestion:
            self.addTag(selected_suggestion)
            self.last_tag = selected_suggestion
            widget.delete(0, tk.END)
            self.validate()
            return

        entry_value = widget.get()
        if entry_value:
            self.addTag(entry_value)
            self.last_tag = entry_value
            widget.delete(0, tk.END)
            self.validate()
            return

        self.event_generate("<<DWIM>>")

    def load_suggestions(self, event=None):
        # print("Loading suggestions...")
        self.all_tags = tuple(t.value for t in logic.search_tags_re('*', subpattern=None, display_type='display'))
        # pprint.pprint(self.all_tags)

    def show_suggestions(self, event=None):
        if len(self.all_tags) < 1:
            return

        query = self.entry_add.get()
        if query == self.last_query:
            return

        self.listbox_suggestion.delete(0, self.listbox_suggestion.size())

        if len(query) < 2:
            return

        matches = getMatches(query, self.all_tags, fuzzy=True)

        for tag in matches.all:
            self.listbox_suggestion.insert(tk.END, tag)
            self.listbox_suggestion.itemconfig(tk.END,
                foreground=logic.get_tag_color(tag),
            )

        self.last_query = query

        if self.aggressive.get():
            self.suggestion_nav.set(0)

        else:
            self.suggestion_nav.set(-1)

