import logging
import pprint
import threading
import tkinter as tk
from collections.abc import Sequence
from tkinter import TclError, ttk

from hydrustools import logic
from hydrustools.component import fuzzysearch
from hydrustools.component.fuzzysearch import MatchResults, getMatches

from .gui_util import tkwrapc


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
                foreground=logic.get_tag_color(value),
            )


class TagEditorList(ttk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.tag_list = []
        self.modified = False

        self.all_tags: Sequence[str] = []
        self.tag_context: tuple[str, ...] = ()
        self.tag_synonyms: dict[str, str] = {}

        self.last_query = ""
        self.last_tag: str | None = None

        self.aggressive = tk.BooleanVar(value=True)

        self.initwindow()

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

        self.load_context_suggestions()
        self.validate()

    def addTag(self, new_tag: str):
        if new_tag not in self.tag_list:
            self.tag_list.append(new_tag)
            self.listbox_taglist.insert(tk.END, new_tag)
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
            if selected_suggestion.startswith("-"):
                # Delete command
                self.removeTag(selected_suggestion[1:])
            else:
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
        self.logger.info("Loading global suggestions...")

        self.pb['value'] = 25
        all_tags = tuple(t.value for t in logic.search_tags_re('*', subpattern=None, display_type='display'))

        self.pb['value'] = 50
        self.tag_synonyms = {
            sib: si.ideal_tag
            for si in logic.get_sibling_ideal_targets(all_tags)
            for sib in si.siblings
        }

        self.all_tags = tuple(logic.flatList([
            all_tags,
            self.tag_synonyms.keys()
        ]))

        self.load_context_suggestions()

        # self.all_tags = tuple(logic.flatList([all_tags, self.tag_synonyms.keys()]))
        # pprint.pprint(self.all_tags)

    def load_context_suggestions(self, event=None):
        self.logger.info("Loading context suggestions for %s", self.tag_list)

        self.pb['value'] = 20
        self.sib_info = logic.get_sibling_ideal_targets(self.tag_list)

        self.pb['value'] = 90
        self.tag_context = tuple(logic.flatList(
            [*si.descendants]
            for si in self.sib_info
        ))

        self.pb['value'] = 0
        self.logger.info("Found %s tags in context", len(self.tag_synonyms))

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

        # TODO: This can build on previous results recursively
        matches = fuzzysearch.perfect_search(
            self.all_tags,
            query,
            context=self.tag_context,
            extra_entries=delete_commands,
            limit=20
        )
        # match_values = pfuzzer_search(self.all_tags, query)

        # pprint.pprint(matches)

        suggestions = []
        for tag in matches:
            tag = self.tag_synonyms.get(tag, tag)
            if tag in suggestions:
                # Deduplicate synonyms
                continue
            self.listbox_suggestion.insert(tk.END, tag)
            self.listbox_suggestion.itemconfig(tk.END,
                foreground=logic.get_tag_color(tag),
            )
            suggestions.append(tag)

        self.last_query = query

        if self.aggressive.get():
            self.suggestion_nav.set(0)

        else:
            self.suggestion_nav.set(-1)

