
import logging
import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk
from typing import Any, Callable, Literal, Required, TypedDict


class _TkTreeviewItemDict(TypedDict):
    text: str
    image: list[str] | Literal[""]  # no idea why it's wrapped in list
    values: list[Any] | Literal[""]
    open: bool  # actually 0 or 1
    tags: list[str] | Literal[""]


class TreeListItemDict(TypedDict, total=False):
    id: str | int
    text: str
    image: str
    values: Required[list[Any]]
    tags: str | list[str]


def xstr(s, nonestr=str(None)) -> str:
    if s:
        # Strip invalid characters.
        return "".join([c for c in str(s) if ord(c) in range(65536)])
    else:
        return nonestr



class MultiColumnListbox(tk.Frame):
    """use a ttk.TreeView as a multicolumn ListBox"""

    def __init__(
        self,
        parent,
        headers: list[str],
        tabledata: list[TreeListItemDict] = [],
        multiselect: bool = False,
        sortable: bool = True,
        vscroll: bool = True,
        hscroll: bool = False,
        nonestr: str = "None",
        *args,
        **kwargs,
    ) -> None:
        tk.Frame.__init__(self, parent, *args, **kwargs)

        self.sortable: bool = sortable
        self.headers: list[str] = headers  # This must remain static.
        self.nonestr: str = nonestr

        self.root_item = ''

        self.TkFont = tkFont.Font()
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.tree: ttk.Treeview

        self.setup_widgets(vscroll=vscroll, hscroll=hscroll)
        self.build_tree(tabledata)

        if multiselect:
            self.tree.configure(selectmode=tk.NONE)
            self.bindSelectionActionUID("<Button-1>", self.tree.selection_toggle)
            # self.tree.bind("<Button-1>", self.handle_multiselect_click)

    def bindSelectionAction(
        self,
        binding: str | None,
        callback: Callable[[_TkTreeviewItemDict], Any],
    ) -> None:
        def cb(event: tk.Event) -> Any:
            item: _TkTreeviewItemDict = self.tree.item(self.tree.identify("item", event.x, event.y))
            return callback(item)

        self.tree.bind(binding, cb)

    def bindSelectionActionUID(
        self,
        binding: str | None,
        callback: Callable[[str], Any],
    ) -> None:
        def cb(event: tk.Event) -> Any:
            desc = self.tree.identify("item", event.x, event.y)
            return callback(desc)

        self.tree.bind(binding, cb)

    def setup_widgets(self, vscroll=True, hscroll=True) -> None:
        container: tk.Frame = self

        # Create a treeview with dual scrollbars
        self.tree: ttk.Treeview = ttk.Treeview(self, columns=self.headers, selectmode=tk.EXTENDED, show="headings")
        self.tree.grid(column=0, row=0, sticky="nsew")

        if vscroll:
            vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
            vsb.grid(column=1, row=0, sticky="ns")
            self.tree.configure(yscrollcommand=vsb.set)
        if hscroll:
            hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
            hsb.grid(column=0, row=1, sticky="ew")
            self.tree.configure(xscrollcommand=hsb.set)

        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

    def sortby(self, tree: ttk.Treeview, col: str, descending: int) -> None:
        """sort tree contents when a column header is clicked on"""

        data: list[tuple[Any, str]] = [
            (tree.set(child, col), child)
            for child in tree.get_children(self.root_item)
        ]

        # if the data to be sorted is numeric change to float
        if all(val.isnumeric() for val, id in data):
            # is_numeric = True
            for i in range(len(data)):
                data[i] = (float(data[i][0]), data[i][1])

        # now sort the data in place
        data.sort(reverse=bool(descending))
        for index, item in enumerate(data):
            tree.move(item[1], "", index)

        # switch the heading so it will sort in the opposite direction
        tree.heading(col, command=lambda col=col: self.sortby(tree, col, int(not descending)))

    def delete_all(self):
        self.tree.delete(*self.tree.get_children())

    def insert_item(self, item: TreeListItemDict) -> str:
        # Sanitize value strings
        if item.get("values"):
            item["values"] = [xstr(s, nonestr=self.nonestr) for s in item["values"]]

        return self.tree.insert(self.root_item, tk.END, **item)

    def build_tree(self, itemlist: list[TreeListItemDict], resize=True) -> None:
        for col in self.headers:
            if self.sortable:
                self.tree.heading(col, text=col.title(), command=lambda c=col: self.sortby(self.tree, c, 0))
            else:
                self.tree.heading(col, text=col.title())

        for item in itemlist:
            self.insert_item(item)

        if resize:
            self.winfo_toplevel().after(10, self.resize_cols)

    def resize_cols(self):
        for col in self.headers:
            self.tree.column(col, width=self.TkFont.measure(col.title()))

        avgs = [0] * len(self.headers)

        for itemid in self.tree.get_children(""):
            item = self.tree.set(itemid)
            # adjust column's width if necessary to fit each value
            for index, val in enumerate(item.values()):
                if val and val != "":
                    col_w = self.TkFont.measure(val)
                    avgs[index] = (col_w + avgs[index]) // 2

        for i in range(0, len(self.headers)):
            self.tree.column(self.headers[i], width=min(int(avgs[i]), 480))


    def update_tree(self, itemlist: list[TreeListItemDict], resize=True) -> None:
        self.tree.delete(*self.tree.get_children())
        # if len(itemlist) > 100:
        #     self.root_item = self.insert_item({"values": ["<Container>"]})
        # else:
        #     self.root_item = ''

        self.tree.item(self.root_item, open=False)
        for item in itemlist:
            self.insert_item(item)
        self.tree.item(self.root_item, open=True)
        if resize:
            self.winfo_toplevel().after(10, self.resize_cols)

    def modSelection(self, selectionNos: list[int]) -> None:
        select_these_items: list[str] = [
            child for child in self.tree.get_children(self.root_item)
            if int(self.tree.set(child, "ID")) in selectionNos
        ]
        self.tree.selection_set(select_these_items)
        # self.tree.selection_set()

    def getSelectionInts(self) -> list[int]:
        return [
            int(self.tree.set(child, "ID"))
            for child in self.tree.selection()
        ]

    def getSelectionDicts(self) -> list[dict]:
        return [
            self.tree.set(child)
            for child in self.tree.selection()
        ]
