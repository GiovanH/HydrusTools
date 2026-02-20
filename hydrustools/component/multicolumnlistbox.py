
from abc import abstractmethod
from collections import Counter, OrderedDict
import logging
import pprint
import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk
from typing import Any, Callable, ClassVar, Generic, Literal, Required, TypeVar, TypedDict
from PIL import ImageTk


class _TkTreeviewItemDict(TypedDict):
    text: str
    image: list[str] | Literal[""]  # no idea why it's wrapped in list
    values: list[Any] | Literal[""]
    open: bool  # actually 0 or 1
    tags: list[str] | Literal[""]


class TreeListItemDict(TypedDict, total=False):
    id: str | int
    text: str
    image: str | ImageTk.PhotoImage
    values: Required[list[Any]]
    tags: str | list[str]


def xstr(s, nonestr=str(None)) -> str:
    if s is not None:
        # Strip invalid characters.
        return "".join([c for c in str(s) if ord(c) in range(65536)])
    else:
        return nonestr

T = TypeVar('T')

class TreeviewSchema(Generic[T]):
    # Map column ids to labels
    headers: ClassVar[OrderedDict[str, str | None]]
    imagesize: tuple[int, int] | None = None

    columns: ClassVar[tuple[str, ...]]
    displaycolumns: ClassVar[tuple[str, ...]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls.columns = tuple(cls.headers.keys())
        cls.displaycolumns = tuple([
            column for (column, label) in cls.headers.items()
            if label is not None
        ])

    @staticmethod
    @abstractmethod
    def to_tree_item(item: T) -> TreeListItemDict: pass


class MultiColumnListbox(ttk.Frame, Generic[T]):
    """use a ttk.TreeView as a multicolumn ListBox"""

    def __init__(
        self,
        parent,
        schema: type[TreeviewSchema[T]],
        multiselect: bool = False,
        sortable: bool = True,
        vscroll: bool = True,
        hscroll: bool = False,
        nonestr: str = "None",
        # *args,
        # **kwargs,
    ) -> None:
        super().__init__(parent) # , *args, **kwargs)

        self.schema: type[TreeviewSchema[T]] = schema
        self.sortable: bool = sortable
        self.nonestr: str = nonestr

        self.root_item = ''

        self.TkFont = tkFont.Font()
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.tree: ttk.Treeview

        self.setup_widgets(vscroll=vscroll, hscroll=hscroll)

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
            if hasattr(event, 'x'):
                desc = self.tree.identify("item", event.x, event.y)
                return callback(desc)
            else:
                pprint.pprint(event)

        self.tree.bind(binding, cb)

    def setup_widgets(self, vscroll=True, hscroll=True) -> None:
        container: ttk.Frame = self

        # Create a treeview with dual scrollbars. Enable the tree column
        # ("#0") so images provided via the `image` insert argument are shown.
        # Configure a Treeview style with a larger rowheight so tall thumbnails fit.
        style = ttk.Style(self)

        show = "headings"

        margin: int = 0
        image_height = 0
        stylename = "MCL.Treeview"

        if self.schema.imagesize:
            image_height = self.schema.imagesize[1]
            stylename = f"MCL{image_height}.Treeview"
            style.configure(stylename, rowheight=image_height)
            style.configure(stylename, indent=0)
            style.layout(f'{stylename}.Item', [
                ('Treeitem.padding', {'sticky': 'nswe', 'children': [
                    # Indicator removed here
                    ('Treeitem.image', {'side': 'left', 'sticky': ''}),
                ]})
            ])
            margin = 4
            show = "tree headings"

        self.logger.debug("Setting up frame with image config", self.schema.imagesize, "and headers", self.schema.headers, show, stylename)

        self.tree = ttk.Treeview(
            self,
            columns=self.schema.columns,
            selectmode=tk.EXTENDED,
            show=show,
            style=stylename
        )

        if self.schema.imagesize:
            self.logger.debug(f"Adding col #0 for image {self.schema.imagesize}")
            # Configure the tree column for image previews (make width match rowheight)
            self.tree.column("#0", width=(2*margin)+self.schema.imagesize[0], anchor="center", stretch=False)
            self.tree.heading("#0", text="")

        def set_columns():
            display_columns = self.schema.displaycolumns
            try:
                # self.tree.config(columns=self.schema.columns)
                self.tree.config(displaycolumns=display_columns)
            except:
                self.logger.error("Display Columns: %s", display_columns)
                self.logger.error("Columns: %s", self.tree['column'])
                # self.after_idle(set_columns)
                raise

        # self.tree.after_idle(set_columns)
        set_columns()

        self.tree.grid(column=0, row=0, sticky="nsew")


        if vscroll:
            vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
            vsb.grid(column=1, row=0, sticky="ns")
            self.tree.configure(yscrollcommand=vsb.set)
        if hscroll:
            hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
            hsb.grid(column=0, row=1, sticky="ew")
            self.tree.configure(xscrollcommand=hsb.set)

        for col, label in self.schema.headers.items():
            if col not in self.schema.displaycolumns:
                self.logger.debug("Not adding header for col %s, not in %s", col, self.schema.displaycolumns)
                continue
            if label is None:
                self.logger.info("Not adding header for col %s, label is None: %s", col, label)
                continue

            self.tree.column(col, width=self.TkFont.measure(label))
            if self.sortable:
                self.tree.heading(col, text=label, command=lambda c=col: self.sortby(self.tree, c, 0))
            else:
                self.tree.heading(col, text=label)

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
        for item in itemlist:
            self.insert_item(item)

        if resize:
            self.winfo_toplevel().after_idle(self.resize_cols)

    def resize_cols(self):
        self.logger.info("Resizing...")

        for col in self.schema.displaycolumns:
            label = self.schema.headers.get(col)
            assert isinstance(label, str)
            # self.tree.column(col, width=self.TkFont.measure(label))

        avgs = Counter(self.schema.displaycolumns)

        for itemid in self.tree.get_children(""):
            item = self.tree.set(itemid)
            # adjust column's width if necessary to fit each value
            for key in self.schema.displaycolumns:
                val = item[key]
                if val and val != "":
                    col_w = self.TkFont.measure(val)
                    avgs[key] += col_w

        total_children = len(self.tree.get_children(""))
        if total_children == 0:
            return

        # total_children *= 10

        for key, width in avgs.items():
            # self.logger.info(f"{key}, {width}, {total_children}, {width//total_children}")
            self.tree.column(key, width=min(width//total_children, 200))

        self.logger.info("Resized")


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
            self.winfo_toplevel().after_idle(self.resize_cols)

    def modSelection(self, selectionNos: list[int]) -> None:
        select_these_items: list[str] = [
            child for child in self.tree.get_children(self.root_item)
            if int(self.tree.set(child, "ID")) in selectionNos
        ]
        self.tree.selection_set(select_these_items)
        # self.tree.selection_set()

    def getSelectionIDs(self) -> tuple[str, ...]:
        return self.tree.selection()

    def getAllIds(self) -> tuple[str, ...]:
        return self.tree.get_children()

    def getSelectionDicts(self) -> list[dict]:
        return [
            self.tree.set(child)
            for child in self.tree.selection()
        ]

    def getAllDicts(self) -> list[dict]:
        return [
            self.tree.set(child)
            for child in self.tree.get_children()
        ]

