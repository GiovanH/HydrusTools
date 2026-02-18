import dataclasses
import re
import tkinter as tk
from collections import OrderedDict
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import ClassVar

from .. import logic
from ..component.gui_util import Increment, QueryHistory, RegexEntry, pb_iter, tkwrap, tkwrapc
from ..component.multicolumnlistbox import MultiColumnListbox, TreeListItemDict, TreeviewSchema
from ..component.toolwindow import ToolWindow
from ..logic import SiblingInfo, TagInfo
from ..settings import Settings


@dataclass
class RelFlattenAction():
    source_tag: str
    ideal_tag: str
    source_count: int

class RelFlattenActionSchema(TreeviewSchema[RelFlattenAction]):
    headers: ClassVar[OrderedDict[str, str | None]] = OrderedDict([
        ('source_tag', 'Source Tag'),
        ('ideal_tag', 'Ideal Tag'),
        ('source_count', 'Count'),
    ])

    @staticmethod
    def to_tree_item(item: RelFlattenAction) -> TreeListItemDict:
        return {
            "values": [*dataclasses.astuple(item)]
        }


class SiblingFlattenWin(ToolWindow):  # noqa: PLR0904
    helpstr = """Flatten tag siblings.

Select the specific relationships to flatten and click the flatten button to commit changes.

In effect, this finds all images with the source tag directly specified and replaces that with the ideal tag as defined by the sibling relationship.

Presearch searches Hydrus for tags (* will only work if specified in the tag repo settings). Refinement filters that list to only tags matching the given expression. Presearch is fastest!
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_presearch: tk.StringVar = Settings.boundTkVar(self, 'flatten_presearch')
        self.textvar_search: tk.StringVar = Settings.boundTkVar(self, 'flatten_search')

        self.initwindow()

        self.startTask(self.doSearch)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Flatten Tags")
        self.geometry("970x570")

        # self.columnconfigure(0, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame_top, cx, _):
            frame_top.pack(side=tk.TOP, fill=tk.X)

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=1)

            tk.Label(frame_top, text="Presearch substring:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = QueryHistory(
                frame_top, font=('Courier', 10),
                textvariable=self.textvar_presearch,
                hist_store=Settings.boundTkVar(self, 'flatten_presearch_hist')
            )
            entry_search.grid(column=cx.value, row=1, sticky="ew")

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=2)

            tk.Label(frame_top, text="Regex refinement:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = RegexEntry(
                frame_top,
                textvariable=self.textvar_search,
                hist_store=Settings.boundTkVar(self, 'flatten_search_hist')
            )
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startSearch)

            cx.inc()
            btn_search = ttk.Button(frame_top, text="Search", command=self.startSearch)
            btn_search.grid(column=cx.value, row=1, sticky="ew")

            # frame_top.rowconfigure(index=counter_frame.inc(), weight=1)

        # Right
        self.tree_tags = MultiColumnListbox(self, schema=RelFlattenActionSchema)
        self.tree_tags.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        with tkwrap(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as frame_bottom:
            frame_bottom.pack(side=tk.BOTTOM, fill=tk.X)

            self.pb = ttk.Progressbar(frame_bottom, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.pack(side=tk.LEFT, fill=tk.Y)

            ttk.Label(frame_bottom, textvariable=self.textvar_status).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            btn_flatten = ttk.Button(frame_bottom, text="Flatten!", command=self.startTaskCurry(self.doFlatten), width=40)
            btn_flatten.pack(side=tk.RIGHT, fill=tk.Y)

    def startSearch(self, event=None):
        self.startTask(self.doSearch)

    def doSearch(self, event=None):
        search_query: str = self.textvar_presearch.get() or "*"
        search_refinement: str = self.textvar_search.get()

        self.pb['value'] = 25
        self.setStatus(f"Searching {search_query!r} for {search_refinement!r}")

        self.tree_tags.delete_all()
        # self.tree_tags.delete(*self.tree_tags.get_children())

        try:
            results: list[TagInfo] = logic.search_tags_re(search_query, search_refinement)
        except re.error as e:  # noqa: F821
            messagebox.showerror(title="Invalid regex", message=f"Error parsing {search_refinement!r}\n{e}")
            return

        tag_count = {
            tag.value: tag.count
            for tag in results
        }

        self.pb['value'] += 25
        targets: list[SiblingInfo] = logic.get_sibling_ideal_targets([ti.value for ti in results])
        targets = [t for t in targets if t.tag != t.ideal_tag]

        self.pb['value'] += 25
        for si in sorted(targets, key=lambda si: si.tag):
            self.tree_tags.insert_item(
                RelFlattenActionSchema.to_tree_item(
                    RelFlattenAction(
                si.tag, si.ideal_tag,
                tag_count[si.tag]
                    )
                )
            )

        self.winfo_toplevel().after(10, self.tree_tags.resize_cols)

        self.pb['value'] = 0
        self.setStatus(f"Found {len(targets)} siblings")

    def doFlatten(self, event=None):
        selection: list[tuple[str, str]] = [
            (d['source_tag'], d['ideal_tag'])
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
                for row in pb_iter(self.pb, selection):
                    source_tag, ideal_tag = row
                    logic.replace_tag(source_tag, [ideal_tag])
            # self.enable()

            self.startTask(self.doSearch)