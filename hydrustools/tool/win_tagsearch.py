import re
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .. import logic
from ..component.gui_util import Increment, TextCopyWindow, tkwrap, tkwrapc
from ..component.multicolumnlistbox import MultiColumnListbox
from ..component.toolwindow import ToolWindow
from ..logic import TagInfo
from ..settings import HTSettings

Settings = HTSettings()

HEAD_NAME = "Tag Name"
HEAD_COUNT = "Count"

class TagSearchWindow(ToolWindow):  # noqa: PLR0904
    helpstr = """Bulk search and edit tags.

Tag Query searches the tag list, regex refinment filters further.

AND/OR opens search page for all images with the selected tags.

"Map Siblings to Namespace" prompts for a namespace, then gives you an importable clipboard setting that will add the ideal sibling {namespace}:{tag} for each selected {tag}.

"Delete selected tag" removes all occurrences of the selected tags from all images.
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.table_headings = [HEAD_NAME, HEAD_COUNT]

        self.textvar_presearch: tk.StringVar = Settings.boundTkVar(self, 'tagsearch_presearch')
        self.textvar_search: tk.StringVar = Settings.boundTkVar(self, 'tagsearch_search')

        self.boolvar_localonly = Settings.boundTkVar(self, 'tagsearch_localonly', tk.BooleanVar)

        self.initwindow()

        self.startTask(self.doSearch)
        self.mainloop()

    def initwindow(self) -> None:
        self.title("Tag Search")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)

        counter_main_row = Increment()

        # tk.Label(frame_row, text="Match partial string").grid(column=0, row=0, sticky="e")
        # check_partial = ttk.Checkbutton(frame_row, variable=self.boolvar_partial)
        # check_partial.grid(column=1, row=0, sticky="w")

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=8)) as (frame_top, cx, _):
            frame_top.grid(column=0, row=counter_main_row.inc(), sticky="ew", columnspan=2)

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=1)

            tk.Label(frame_top, text="Tag Query:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Entry(frame_top, font=('Courier', 10), textvariable=self.textvar_presearch)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            frame_top.columnconfigure(cx.value, weight=2)

            tk.Label(frame_top, text="Regex refinement:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Entry(frame_top, font=('Courier', 10), textvariable=self.textvar_search)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            btn_search = ttk.Button(frame_top, text="Search", command=self.startTaskCurry(self.doSearch))
            btn_search.grid(column=cx.value, row=1, sticky="ew")

            # frame_top.rowconfigure(index=counter_frame.inc(), weight=1)

        # Right
        counter_main_row.inc()
        self.tree_tags = MultiColumnListbox(self, headers=self.table_headings)

        with tkwrap(self.tree_tags) as tree:
            # assert isinstance(tree, ttk.Treeview)
            tree.grid(column=0, row=counter_main_row.value, sticky="nsew")
            self.rowconfigure(counter_main_row.value, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=2)) as (frame_bottom, cx, cy):
            frame_bottom.grid(row=counter_main_row.inc(), columnspan=2, sticky="ew")
            frame_bottom.columnconfigure(0, weight=1)

            ttk.Label(frame_bottom, textvariable=self.textvar_status).grid(row=cx.inc(), sticky="nsew")

            with tkwrapc(ttk.Frame(frame_bottom)) as (frame, ccx, ccy):
                frame.grid(column=cx.inc(), row=0, sticky="nse")

                btn_search = ttk.Button(frame, text="AND search selected", command=self.openPageAnd)
                btn_search.grid(row=ccy.inc(), sticky="nsew")

                btn_search = ttk.Button(frame, text="OR search selected", command=self.openPageOr)
                btn_search.grid(row=ccy.inc(), sticky="nsew")

            # btn_search = ttk.Button(frame_bottom, text="Add Namespace", command=self.addNamespace)
            # btn_search.grid(column=cx.inc(), row=0, sticky="nse")

            btn_search = ttk.Button(frame_bottom, text="Map to siblings with namespace", command=self.addNamespace)
            # btn_search.config(state=tk.DISABLED)
            btn_search.grid(column=cx.inc(), row=0, sticky="nse")

            btn_search = ttk.Button(frame_bottom, text="Delete selected tag", command=self.deleteTags)
            btn_search.grid(column=cx.inc(), row=0, sticky="nse")

    def doSearch(self, event=None):
        search_query: str = self.textvar_presearch.get() or "*"
        search_refinement: str = self.textvar_search.get()
        self.setStatus(f"Searching {search_query!r} for {search_refinement!r}")

        self.tree_tags.delete_all()
        # self.tree_tags.delete(*self.tree_tags.get_children())

        try:
            results: list[TagInfo] = logic.search_tags_re(search_query, search_refinement,  display_type="display")
        except re.error as e:  # noqa: F821
            messagebox.showerror(title="Invalid regex", message=f"Error parsing {search_refinement!r}\n{e}")
            return

        tag_count = {
            tag.value: tag.count
            for tag in results
        }

        # targets: list[SiblingInfo] = logic.get_sibling_ideal_targets([ti.value for ti in results])

        def _apply():
            self.tree_tags.update_tree([
                {"values": [t.value, t.count]} for t in
                sorted(results, key=lambda ti: ti.value)
            ])

        if len(results) > 200:
            self.after(10, _apply)
        else:
            _apply()
        # for t in
        #     # self.tree_tags.insert('', tk.END, values=row)
        #     self.tree_tags.insert_item({"values": row})
        #     if self.abort_threads: return

        self.winfo_toplevel().after(10, self.tree_tags.resize_cols)

        self.setStatus(f"Found {len(results)} tags")

    def openPageAnd(self, event=None):
        return self.openPage(OR=False)

    def openPageOr(self, event=None):
        return self.openPage(OR=True)

    def openPage(self, OR=False):
        selection: list[str] = [
            d[HEAD_NAME]
            for d in self.tree_tags.getSelectionDicts()
        ]
        self.setStatus(f"Gathered {len(selection)} tags")

        tag_domain = None
        if self.boolvar_localonly.get():
            tag_domain = logic.local_tags_service_key

        query = selection
        if OR:
            query = [query]

        matching_ids = logic.client.search_files(
            tags=query, # type: ignore
            tag_service_key=tag_domain,
            return_file_ids=True
        )['file_ids']
        self.logger.info(matching_ids)
        self.setStatus(f"Got {len(matching_ids)} from search")

        logic.client.add_popup("Tag Search", files_label=f"{selection!r}", file_ids=matching_ids)

    def addNamespace(self, OR=False):
        selection: list[str] = [
            d[HEAD_NAME]
            for d in self.tree_tags.getSelectionDicts()
        ]
        self.setStatus(f"Gathered {len(selection)} tags")

        resp = simpledialog.askstring("Namespace?", "Namespace name")
        if not resp:
            return

        resp = resp.replace(':', '').strip()
        pairs = [
            (tag, f"{resp}:{tag}")
            for tag in selection
        ]

        clip_import = '\n'.join(
            f"{source}\n{ideal}"
            for (source, ideal) in pairs
        )

        TextCopyWindow(clip_import)
        # TODO: Use clipboard format for this
        # Format is:

        # explaination = '\n'.join(f'{source} -> {ideal}' for (source, ideal) in pairs)
        # user_confirmed = messagebox.askyesno(
        #     title="Confirm",
        #     message=f"{explaination}\n\nReplace these tags? This cannot be undone!\n\nSiblings cannot yet be set via the API."
        # )
        # if user_confirmed:
        #     with self.lock():
        #         for row in pairs:
        #             source_tag, ideal_tag = row
        #             logic.replace_tag(source_tag, [ideal_tag])

    def deleteTags(self, OR=False):
        selection: list[str] = [
            d[HEAD_NAME]
            for d in self.tree_tags.getSelectionDicts()
        ]
        self.setStatus(f"Gathered {len(selection)} tags")

        explaination = '\n'.join(selection)
        user_confirmed = messagebox.askyesno(
            title="Confirm",
            message=f"Are you sure you want to remove all instances of the following tags from all images?\n\n{explaination}"
        )
        if user_confirmed:
            with self.lock():
                for tag_name in selection:
                    logic.replace_tag(tag_name, [])
            # self.enable()

            self.startTask(self.doSearch)