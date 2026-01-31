
import logging
import tkinter as tk
from tkinter import ttk

from hydrustools.gui_util import tkwrapc

logging.basicConfig(level=logging.INFO)

class TagEditorList(ttk.Frame):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.logger = logging.getLogger(self.__class__.__name__)
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