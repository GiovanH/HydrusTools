import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .. import logic
from ..component.gui_util import Increment, TextCopyWindow, tkwrap, tkwrapc
from ..component.multicolumnlistbox import MultiColumnListbox
from ..component.toolwindow import ToolWindow
from ..logic import TagInfo
from ..settings import Settings

# HEAD_TAG = "Tag"
HEAD_COUNT = "Count"

class TagRelationshipsWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """TODO"""
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.headers = [HEAD_COUNT]

        self.initwindow()

        self.startTask(self.doSearch)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Tag Relationships")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()


        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as (container, cx, cy):
            container.grid(column=0, row=counter_main_row.inc())

            self.tree: ttk.Treeview = ttk.Treeview(self, columns=self.headers, show="tree headings")
            self.tree.grid(column=0, row=0, sticky="nsew")

        # if vscroll:
            vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
            vsb.grid(column=1, row=0, sticky="ns")
            self.tree.configure(yscrollcommand=vsb.set)
        # if hscroll:
            hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
            hsb.grid(column=0, row=1, sticky="ew")
            self.tree.configure(xscrollcommand=hsb.set)

            sortable = False
            for col in self.headers:
                # if sortable:
                #     self.tree.heading(col, text=col.title(), command=lambda c=col: self.sortby(self.tree, c, 0))
                # else:
                    self.tree.heading(col, text=col.title())

            container.grid_columnconfigure(0, weight=1)
            container.grid_rowconfigure(0, weight=1)


        self.rowconfigure(counter_main_row.value, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as (frame_bottom, cx, cy):
            frame_bottom.grid(row=counter_main_row.inc(), columnspan=2, sticky="ew")

            self.pb = ttk.Progressbar(frame_bottom, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=cx.inc(), row=0, sticky="ns")

            ttk.Label(frame_bottom, textvariable=self.textvar_status).grid(column=cx.inc(), row=0, sticky="nsew")
            frame_bottom.columnconfigure(cx.value, weight=1)

    def doSearch(self, event=None):
        self.setStatus("Getting tag list")
        all_tags = logic.search_tags_re("b*", subpattern=None)
        all_tags_set = {ti.value for ti in all_tags}
        # all_tags_map = {ti.value: ti for ti in all_tags}

        self.setStatus(f"Getting relationships among {len(all_tags)} tags")
        unnamespaced_tags = [t for t in all_tags_set if ':' not in t]
        sibling_resp = logic.get_sibling_ideal_targets(unnamespaced_tags)
        all_relationships_list = sibling_resp
        # all_relationships_map: dict[str, logic.SiblingInfo] = {
        #     **{
        #         s: si
        #         for si in
        #         sibling_resp
        #         for s in si.siblings
        #     }
        # }
        self.setStatus(f"Fetched {len(all_relationships_list)} relationships")

        children = set()
        for si in sorted(all_relationships_list, key = lambda si: si.ideal_tag):
            print(si)

            if len(si.ancestors) == 0 and si.ideal_tag not in children:
                self.tree.insert(
                    '', index=tk.END,
                    id=si.ideal_tag,
                    text=si.ideal_tag,
                    values = ["", si.ideal_tag, len(si.descendants)],
                    open=True
                )
                children.add(si.ideal_tag)

                if len(si.siblings) > 1:
                    fldr_siblings = self.tree.insert(
                        si.ideal_tag, index=tk.END,
                        text="Siblings",
                        values = [len(si.siblings)],
                        open=True
                    )
                    for alias in si.siblings:
                        if alias == si.ideal_tag:
                            continue
                        self.tree.insert(
                            fldr_siblings, index=tk.END,
                            # id=si.ideal_tag,
                            text=alias
                            # values = ["sibling", alias, ""]
                        )
                if len(si.descendants) > 0:
                    fldr_descendants = self.tree.insert(
                        si.ideal_tag, index=tk.END,
                        text="Children",
                        values = [len(si.descendants)],
                        open=True
                    )
                    for alias in si.descendants:
                        self.tree.insert(
                            fldr_descendants, index=tk.END,
                            # id=si.ideal_tag,
                            text=alias
                            # values = ["sibling", alias, ""]
                        )


                # for child in si.descendants:
                #     if child not in children:
                #         self.tree.insert(
                #             si.ideal_tag, index=tk.END,
                #             id=child,
                #             values = ["child", child, '']
                #         )
                #         children.add(child)

        print(self.tree.get_children())
