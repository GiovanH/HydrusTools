import logging
import pprint
import threading
import tkinter as tk
from collections.abc import Sequence
from tkinter import TclError, ttk

from frozendict import frozendict

from hydrustools.utils import hydrus
from hydrustools.utils import fuzzysearch
from hydrustools.utils.util import timer

from ..utils.gui_util import tkwrapc

# def penalize_ships(tup: tuple[fuzzysearch.Score, str]):
#     if tup[1].startswith("ship:"):
#         return (tup[0]-1, tup[1])
#     return tup

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

class TagList(tk.Listbox):
    def __init__(self, *args, **kwargs) -> None:
        kwargs['selectmode'] = tk.EXTENDED
        super().__init__(*args, **kwargs)

    def insert(self, index, *elements):
        for value in elements:
            super().insert(index, value)
            self.itemconfig(tk.END,
                foreground=hydrus.get_tag_color(value),
            )


class TagEditorList(ttk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.tag_list = []
        self.modified = False

        self.all_tags: Sequence[str] = []
        self.all_tag_counts: frozendict[str, int]
        self.tag_context: tuple[str, ...] = ()
        self.tag_synonyms_all: dict[str, str] = {}

        self.last_query = ""
        # self.last_tag: str | None = None

        self.aggressive = tk.BooleanVar(value=True)

        self.initwindow()

        # self.event_add("<<Modified>>")
        # self.event_add("<<DWIM>>")
        # self.event_add("<<TagAdd>>")

        self.suggestion_nav = ListboxNavigator(self.listbox_suggestion)

        self.bind_controls()

        self.pb: ttk.Progressbar | dict = {"value": 0}

        threading.Thread(target=self.load_suggestions, daemon=True).start()


    def initwindow(self) -> None:
        with tkwrapc(self) as (frame, cx, cy):
            # tk.Label(frame, text="Merged tags").grid(column=0, row=cy.inc(), sticky="ew")
            self.listbox_taglist = TagList(frame)
            self.listbox_taglist.grid(column=0, row=cy.inc(), sticky="nsew")
            frame.rowconfigure(index=cy.value, weight=1)
            frame.columnconfigure(index=0, weight=1)

            self.listbox_taglist.bind('<Delete>', self.removeSelectedTags)
            self.listbox_taglist.bind('<Double-Button-1>', self.removeSelectedTags)

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

    #     self.entry_add.bind("<Control-period>", self.try_repeat)

    # def try_repeat(self, event=None):
    #     if self.last_tag:
    #         self.addTag(self.last_tag)

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

        for tag in hydrus.sort_tags(tag_list):
            self.addTag(tag, interactive=False)
            # self.listbox_taglist.insert(tk.END, tag)

        self.load_context_suggestions()
        self.validate()

    def addTag(self, new_tag: str, interactive=True):
        if new_tag not in self.tag_list:
            self.tag_list.append(new_tag)
            self.listbox_taglist.insert(tk.END, new_tag)
            self.modified = True
            self.event_generate("<<Modified>>")
        if interactive:
            self.last_tag = new_tag
            self.event_generate("<<TagAdd>>")

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
            if selected_suggestion.startswith("-"):
                # Delete command
                self.removeTag(selected_suggestion[1:])
            else:
                self.addTag(selected_suggestion)
                # self.last_tag = selected_suggestion
            widget.delete(0, tk.END)
            self.validate()
            return

        entry_value = widget.get()
        if entry_value:
            self.addTag(entry_value)
            # self.last_tag = entry_value
            widget.delete(0, tk.END)

            self.add_single_tag_to_context(entry_value)

            self.validate()
            return

        self.event_generate("<<DWIM>>")

    def load_suggestions(self, event=None):
        self.logger.info("Loading global suggestions...")

        self.pb['value'] = 25
        all_tag_counts = hydrus.search_tags_re('*', subpattern=None, display_type='display')

        all_tags = tuple(t.value for t in all_tag_counts if t.count > 0)

        self.pb['value'] = 50
        self.tag_synonyms_all = {
            sib: si.ideal_tag
            for si in hydrus.get_sibling_ideal_targets(all_tags)
            for sib in si.siblings
            if sib != si.ideal_tag
        }

        # pprint.pprint(self.tag_synonyms_all)

        self.all_tags = tuple([
            *all_tags,
            *self.tag_synonyms_all.keys()
        ])

        self.all_tag_counts = frozendict({
            t.value: t.count
            for t in all_tag_counts
        })

        # pprint.pprint(self.all_tags)

        with timer("load tag context", min_secs=0.1):
            self.load_context_suggestions()


    def load_context_suggestions(self, event=None):
        self.logger.info("Loading context suggestions for %s", self.tag_list)

        self.pb['value'] = 20
        sib_info = hydrus.get_sibling_ideal_targets(self.tag_list)

        self.pb['value'] = 90
        self.tag_context = tuple(hydrus.flatList(
            [*si.descendants]
            for si in sib_info
            if si.ideal_tag in self.tag_list
        ))

        self.pb['value'] = 0
        self.logger.info("Found %s descendant tags in context", len(self.tag_context))

    def add_single_tag_to_context(self, new_tag):
        # Add new tag to context
        self.all_tags = (
            new_tag,
            *self.all_tags,
        )

    def show_suggestions(self, event=None):
        if len(self.all_tags) < 1:
            return

        query = self.entry_add.get()
        if query == self.last_query:
            return

        self.listbox_suggestion.delete(0, self.listbox_suggestion.size())

        if len(query) < 2:
            return

        delete_commands = tuple(f"-{t}" for t in self.tag_list)

        with timer(f"all {len(self.all_tags)}", min_secs=0, logger=self.logger.info):
            match_all = fuzzysearch.perfect_search(
                self.all_tags,
                query,
                limit=40
            )

        with timer(f"commands {len(delete_commands)}", min_secs=0, logger=self.logger.info):
            match_commands = fuzzysearch.perfect_search(
                delete_commands,
                query
            )

        with timer(f"context {len(self.tag_context)}", min_secs=0, logger=self.logger.info):
            match_context = fuzzysearch.perfect_search(
                self.tag_context,
                query,
                score_bonus=10
            )

        # TODO: This can build on previous results recursively
        with timer("merge", min_secs=0, logger=self.logger.info):
            matches = fuzzysearch.merge_lists(
                match_all, match_commands, match_context,
                count_tiebreak=self.all_tag_counts,
                # edits=[penalize_ships]
            )

        suggestions = []
        for tag in matches:
            syno = self.tag_synonyms_all.get(tag)
            if syno:
                # self.logger.info("%s is synonym of %s", syno, tag)
                tag = syno
            if tag in suggestions:
                # Deduplicate synonyms
                continue
            self.listbox_suggestion.insert(tk.END, tag)
            self.listbox_suggestion.itemconfig(tk.END,
                foreground=hydrus.get_tag_color(tag),
            )
            suggestions.append(tag)

        self.last_query = query

        if self.aggressive.get():
            self.suggestion_nav.set(0)

        else:
            self.suggestion_nav.set(-1)

