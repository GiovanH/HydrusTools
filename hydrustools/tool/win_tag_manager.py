from collections import OrderedDict
import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import ClassVar

from .. import logic
from ..component.gui_util import QueryHistory, RegexEntry, TextCopyWindow, tkwrap, tkwrapc
from ..component.multicolumnlistbox import MultiColumnListbox, TreeListItemDict, TreeviewSchema
from ..component.toolwindow import ToolWindow
from ..logic import TagInfo
from ..settings import Settings


class TagSchema(TreeviewSchema[TagInfo]):
    headers: ClassVar[OrderedDict[str, str | None]] = OrderedDict([
        ('name', 'Tag name'),
        ('count', 'Count')
    ])

    @staticmethod
    def to_tree_item(item: TagInfo) -> TreeListItemDict:
        return {"values": [item.value, item.count]}


class TagManagerWin(ToolWindow):  # noqa: PLR0904
    helpstr = """Bulk search and edit tags.

Tag Query searches the tag list, regex refinment filters further.

AND/OR opens search page for all images with the selected tags.

"Map Siblings to Namespace" prompts for a namespace, then gives you an importable clipboard setting that will add the ideal sibling {namespace}:{tag} for each selected {tag}.

"Delete selected tag" removes all occurrences of the selected tags from all images.
    """

    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_presearch: tk.StringVar = Settings.boundTkVar(self, "tagsearch_presearch")
        self.textvar_presearch_hist: tk.StringVar = Settings.boundTkVar(self, "tagsearch_presearch_hist")
        self.textvar_search: tk.StringVar = Settings.boundTkVar(self, "tagsearch_search")
        self.textvar_search_hist: tk.StringVar = Settings.boundTkVar(self, "tagsearch_search_hist")

        self.boolvar_localonly = Settings.boundTkVar(self, "tagsearch_localonly", tk.BooleanVar)

        self.initwindow()

        self.startTask(self.doSearch)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Tag Search")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame_top, cx, _):
            frame_top.pack(side=tk.TOP, fill=tk.X)

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=1)

            tk.Label(frame_top, text="Tag Query:").grid(column=cx.value, row=0, sticky="w")

            self.entry_presearch = QueryHistory(
                frame_top,
                font=("Courier", 10),
                textvariable=self.textvar_presearch,
                hist_store=self.textvar_presearch_hist,
            )
            self.entry_presearch.grid(column=cx.value, row=1, sticky="ew")
            self.entry_presearch.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=2)

            tk.Label(frame_top, text="Regex refinement:").grid(column=cx.value, row=0, sticky="w")

            self.entry_filter = RegexEntry(
                frame_top, font=("Courier", 10), textvariable=self.textvar_search, hist_store=self.textvar_search_hist
            )
            self.entry_filter.grid(column=cx.value, row=1, sticky="ew")
            self.entry_filter.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            btn_search = ttk.Button(frame_top, text="Search", command=self.startTaskCurry(self.doSearch))
            btn_search.grid(column=cx.value, row=1, sticky="ew")

        self.tree_tags: MultiColumnListbox[TagInfo] = MultiColumnListbox(self, schema=TagSchema)
        self.tree_tags.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as (frame_bottom, cx, cy):
            frame_bottom.pack(side=tk.BOTTOM, fill=tk.X)

            self.pb = ttk.Progressbar(frame_bottom, orient="vertical", mode="determinate", length=30)
            self.pb.pack(side=tk.LEFT, fill=tk.Y)

            ttk.Label(frame_bottom, textvariable=self.textvar_status).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            with tkwrap(ttk.Frame(frame_bottom)) as frame:
                frame.pack(side=tk.LEFT, fill=tk.Y)

                btn_search = ttk.Button(frame, text="AND search selected", command=self.openPageAnd)
                btn_search.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

                btn_search = ttk.Button(frame, text="OR search selected", command=self.openPageOr)
                btn_search.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            btn_search = ttk.Button(frame_bottom, text="Map to siblings with namespace", command=self.addNamespace)
            btn_search.pack(side=tk.LEFT, fill=tk.Y)

            btn_search = ttk.Button(frame_bottom, text="Delete selected tag", command=self.deleteTags)
            btn_search.pack(side=tk.LEFT, fill=tk.Y)

    def doSearch(self, event=None):
        search_query: str = self.textvar_presearch.get() or "*"
        search_refinement: str = self.textvar_search.get()
        self.setStatus(f"Searching {search_query!r} for {search_refinement!r}")

        self.entry_filter.add_history(search_refinement)
        self.entry_presearch.add_history(search_query)

        self.tree_tags.delete_all()

        try:
            results: list[TagInfo] = logic.search_tags_re(search_query, search_refinement, display_type="display")
        except re.error as e:  # noqa: F821
            messagebox.showerror(title="Invalid regex", message=f"Error parsing {search_refinement!r}\n{e}")
            return

        self.setStatus(f"Found {len(results)} tags. Displaying...")

        def _apply():
            self.tree_tags.update_tree(
                [{"values": [t.value, t.count]} for t in sorted(results, key=lambda ti: ti.value)], resize=False
            )
            self.setStatus("Done")

        if len(results) > 200:
            self.after(10, _apply)
        else:
            _apply()
            self.winfo_toplevel().after(10, self.tree_tags.resize_cols)
            self.setStatus("Done")

    def openPageAnd(self, event=None):
        return self.openPage(OR=False)

    def openPageOr(self, event=None):
        return self.openPage(OR=True)

    def openPage(self, OR=False):
        selection: list[str] = [d["name"] for d in self.tree_tags.getSelectionDicts()]
        self.setStatus(f"Gathered {len(selection)} tags")

        tag_domain = None
        if self.boolvar_localonly.get():
            tag_domain = logic.local_tags_service_key

        query = selection
        if OR:
            query = [query]

        matching_ids = logic.client.search_files(
            tags=query,  # type: ignore
            tag_service_key=tag_domain,
            return_file_ids=True,
        )["file_ids"]
        self.logger.info(matching_ids)
        self.setStatus(f"Got {len(matching_ids)} from search")

        logic.client.add_popup("Tag Search", files_label=f"{selection!r}", file_ids=matching_ids)

    def addNamespace(self, OR=False):
        selection: list[str] = [d["name"] for d in self.tree_tags.getSelectionDicts()]
        self.setStatus(f"Gathered {len(selection)} tags")

        resp = simpledialog.askstring("Namespace?", "Namespace name")
        if not resp:
            return

        resp = resp.replace(":", "").strip()
        pairs = [(tag, f"{resp}:{tag}") for tag in selection]

        clip_import = "\n".join(f"{source}\n{ideal}" for (source, ideal) in pairs)

        TextCopyWindow(clip_import)

    def deleteTags(self, OR=False):
        selection: list[str] = [d["name"] for d in self.tree_tags.getSelectionDicts()]
        self.setStatus(f"Gathered {len(selection)} tags")

        explaination = "\n".join(selection)
        user_confirmed = messagebox.askyesno(
            title="Confirm",
            message=f"Are you sure you want to remove all instances of the following tags from all images?\n\n{explaination}",
        )
        if user_confirmed:
            with self.lock():
                for tag_name in selection:
                    logic.replace_tag(tag_name, [])

            self.startTask(self.doSearch)
