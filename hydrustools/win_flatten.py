import re
import tkinter as tk
from tkinter import messagebox, ttk

from .multicolumnlistbox import MultiColumnListbox

from . import logic
from .gui_util import Increment, tkwrap, tkwrapc
from .logic import SiblingInfo, TagInfo
from .settings import HTSettings
from .toolwindow import ToolWindow

Settings = HTSettings()


class FlattenWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """Flatten tag siblings.

In effect, this finds all images with the source tag directly specified and replaces that with the ideal tag as defined by the sibling relationship.

Select the specific relationships to flatten and click the flatten button to commit changes.

Presearch searches Hydrus for tags (* will only work if specified in the tag repo settings). Refinement filters that list to only tags matching the given expression. Presearch is fastest!
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.table_headings = ["Source Tag", "Ideal", "Count"]

        self.textvar_presearch: tk.StringVar = Settings.boundTkVar(self, 'flatten_presearch')
        self.textvar_search: tk.StringVar = Settings.boundTkVar(self, 'flatten_search')

        self.initwindow()

        self.startTask(self.doSearch)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Flatten Tags")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame_top, cx, _):
            frame_top.grid(column=0, row=counter_main_row.inc(), sticky="ew", columnspan=2)

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=1)

            tk.Label(frame_top, text="Presearch substring:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Entry(frame_top, font=('Courier', 10), textvariable=self.textvar_presearch)
            entry_search.grid(column=cx.value, row=1, sticky="ew")

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=2)

            tk.Label(frame_top, text="Regex refinement:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Entry(frame_top, font=('Courier', 10), textvariable=self.textvar_search)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startSearch)

            cx.inc()
            btn_search = ttk.Button(frame_top, text="Search", command=self.startSearch)
            btn_search.grid(column=cx.value, row=1, sticky="ew")

            # frame_top.rowconfigure(index=counter_frame.inc(), weight=1)

        # Right
        counter_main_row.inc()
        self.tree_tags = MultiColumnListbox(self, headers=self.table_headings)

        with tkwrap(self.tree_tags) as tree:
            # assert isinstance(tree, ttk.Treeview)
            tree.grid(column=0, row=counter_main_row.value, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as frame_bottom:
            frame_bottom.grid(row=counter_main_row.inc(), column=0, columnspan=2, sticky="ew")
            tk.Label(frame_bottom, textvariable=self.textvar_status).grid(column=0, row=0, sticky="sw")

            frame_bottom.columnconfigure(0, weight=1)

            btn_flatten = ttk.Button(frame_bottom, text="Flatten!", command=self.startFlatten)
            btn_flatten.grid(column=1, row=0, sticky="e")

    def startSearch(self, event=None):
        self.startTask(self.doSearch)

    def startFlatten(self, event=None):
        with self.lock():
            self.after(100, self.doFlatten)

    def doSearch(self, event=None):
        search_query: str = self.textvar_search.get()
        self.setStatus(f"Searching {search_query!r}")

        self.tree_tags.delete_all()
        # self.tree_tags.delete(*self.tree_tags.get_children())

        try:
            results: list[TagInfo] = logic.search_tags_re("*", search_query)
        except re.error as e:  # noqa: F821
            messagebox.showerror(title="Invalid regex", message=f"Error parsing {search_query!r}\n{e}")
            return

        tag_count = {
            tag.value: tag.count
            for tag in results
        }

        targets: list[SiblingInfo] = logic.get_sibling_ideal_targets([ti.value for ti in results])

        for si in sorted(targets, key=lambda si: si.tag):
            row = [si.tag, si.ideal_tag, tag_count.get(si.tag)]
            # self.tree_tags.insert('', tk.END, values=row)
            self.tree_tags.insert_item({"values": row})

        self.winfo_toplevel().after(10, self.tree_tags.resize_cols)

        self.setStatus(f"Found {len(targets)} siblings")

    def doFlatten(self, event=None):
        # selection = [
        #     (row['Source Tag'], row['Ideal'])
        #     for row in (self.tree_tags.set(child) for child in self.tree_tags.selection())
        # ]
        selection: list[tuple[str, str]] = [
            (d['Source Tag'], d['Ideal'])
            for d in self.tree_tags.getSelectionDicts()
        ]

        if len(selection) == 0:
            return

        self.logger.info(selection)

        explaination = '\n'.join(f'{source} -> {ideal}' for (source, ideal) in selection)
        user_confirmed = messagebox.askyesno(
            title="Confirm",
            message=f"{explaination}\n\nFlatten these tags? This cannot be undone!"
        )
        if user_confirmed:
            with self.lock():
                for row in selection:
                    source_tag, ideal_tag = row
                    logic.replace_tag(source_tag, [ideal_tag])
            # self.enable()

            self.startTask(self.doSearch)