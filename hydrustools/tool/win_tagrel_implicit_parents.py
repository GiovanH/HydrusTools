from collections import Counter
import pprint
from tkinter import ttk
import tkinter as tk


from ..component.gui_util import pb_iter, tkwrapc
from ..component.relationship_adder import RelationshipAction, RelationshipAdderFrame
from ..component.toolwindow import ToolWindow

from .. import logic
from ..settings import Settings


class ImplicitParentFinderWin(ToolWindow):  # noqa: PLR0904
    helpstr = """Find Implicit Parents

    Some tags have logical implications that are already captured in the data but aren't added as automatic parent relationships yet. This detects those. It's designed to find characters that are almost always found in a specific series, but it can be used with other namespaces as well.

    Parent prefix filter is the tag prefix defining the kind of parent being searched for. Recommendations must have this prefix, and tags that already have a parent with this prefix are considered categorized already.

    Child tag query is the search for child tags to examine. Since this is a search, you can include ":*" if your API supports it.

    Minimum count is the minimum number of times an orphan tag needs to appear to be considered. You can use this to filter out infrequent tags to speed up search time.

    Parent factor defines how much more common a parent tag needs to be than other parent tags to be considered a match. Any potential parent tag needs to be this factor larger than other matching parent tags to be considered.
    """
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)

        self.textvar_ns_parent = Settings.boundTkVar(self, 'findimplicitparent_ns_parent')
        self.textvar_ns_child = Settings.boundTkVar(self, 'findimplicitparent_ns_child')
        self.var_min_count: tk.IntVar = Settings.boundTkVar(self, 'findimplicitparent_min_count', tk.IntVar)
        self.var_tag_factor = Settings.boundTkVar(self, 'findimplicitparent_factor', tk.IntVar)

        self.debug_specific = ['voltron', 'my hero', "todoroki"]

        self.abort_threads = False

        self.initwindow()
        self.bind("<Escape>", self.abort)

        self.startTask(self.doSearch)
        self.mainloop()

    def abort(self, event=None):
        self.abort_threads = True

    def initwindow(self) -> None:
        self.title("Find Implicit Parents")
        self.geometry("970x570")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        with tkwrapc(ttk.Frame(self, relief=tk.GROOVE, padding=4)) as (frame, cx, cy):
            frame.grid(column=0, row=0, sticky="ew")

            cx.inc()
            tk.Label(frame, text="Parent prefix filter:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Entry(frame, textvariable=self.textvar_ns_parent)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            tk.Label(frame, text="Child Tag Query:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Entry(frame, textvariable=self.textvar_ns_child)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            tk.Label(frame, text="Minimum count:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Spinbox(frame, textvariable=self.var_min_count, from_=1, to=500)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            tk.Label(frame, text="Parent factor:")\
                .grid(column=cx.value, row=0, sticky="w")

            entry_search = ttk.Spinbox(frame, textvariable=self.var_tag_factor, from_=1, to=500)
            entry_search.grid(column=cx.value, row=1, sticky="ew")
            entry_search.bind("<Return>", self.startTaskCurry(self.doSearch))

            cx.inc()
            frame.columnconfigure(cx.value, weight=1)

            cx.inc()
            btn_search = ttk.Button(frame, text="Search", command=self.startTaskCurry(self.doSearch))
            btn_search.grid(column=cx.value, row=1, sticky="ew")

        self.frame_ra = RelationshipAdderFrame(self, pack_buttons=False)
        self.frame_ra.grid(column=0, row=1, sticky="nsew")
        self.bind("<Delete>", self.frame_ra.deleteSelected)

        with tkwrapc(ttk.Frame(self)) as (frame, cx, cy):
            frame.grid(column=0, row=2, sticky="ew")

            self.pb = ttk.Progressbar(frame, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.grid(column=cx.inc(), row=0, sticky="ns")

            ttk.Label(frame, textvariable=self.textvar_status).grid(column=cx.inc(), row=0, sticky="nsew")
            frame.columnconfigure(index=cx.value, weight=1)

            btn = self.frame_ra.btn_selected(frame)
            btn.grid(column=cx.inc(), row=0, sticky="nse")

            btn = self.frame_ra.btn_all(frame)
            btn.grid(column=cx.inc(), row=0, sticky="nse")

    def doSearch(self):
        self.abort_threads = False

        min_char_count = self.var_min_count.get()
        first_tag_factor = self.var_tag_factor.get()
        namespace_a = self.textvar_ns_child.get()
        parent_prefix = self.textvar_ns_parent.get()

        self.pb['value'] = 0

        self.pb['value'] += 25
        self.setStatus(f"Looking up all tags matching {namespace_a!r}")
        all_characters = logic.search_tags_re(f"{namespace_a}", subpattern=None)

        self.pb['value'] += 25
        self.setStatus(f"Looking up relationships for {len(all_characters)} tags")
        sibling_resp = logic.get_sibling_ideal_targets([t.value for t in all_characters])
        all_relationships: dict[str, logic.SiblingInfo] = {
            **{
                s: si
                for si in
                sibling_resp
                for s in si.siblings
            }
        }

        self.pb['value'] += 25
        self.setStatus(f"Identifying orphans among {len(all_characters)} tags")

        orphans = []
        skipped_too_few = 0

        for ci in all_characters:
            log_debug = self.logger.debug
            if any(substr in ci.value for substr in self.debug_specific):
                log_debug = self.logger.warning
                log_debug(f"Triggered extra inspection for {ci}")

            if ci.count < min_char_count:
                log_debug(f"Skipping tag {ci} without {min_char_count} occurrences")
                skipped_too_few += 1
                continue

            si = all_relationships.get(ci.value)
            if not si:
                self.logger.info(f"Adding tag {ci.value} with no relationship data")
                orphans.append(ci.value)
                continue
            if ci.value != si.ideal_tag:
                log_debug(f"Skipping non-ideal tag {ci.value} in {si}")
                continue

            if not ci.value.startswith('character'):
                self.logger.warning(f"Strange tag {ci} returned by hydrus for search {namespace_a}")

            if len(si.ancestors) > 0:
                if parent_prefix and any(a.startswith(parent_prefix) for a in si.ancestors):
                    self.logger.info(f"Skipping tag {ci.value} with known series parent in {si.ancestors}")
                    continue
                self.logger.info(f"Adding known orphan tag {ci.value} with no instance of {parent_prefix}* in {si.ancestors}")
                orphans.append(ci.value)

            self.logger.info(f"Adding known orphan tag {ci.value} with no ancestors")
            orphans.append(ci.value)

        if skipped_too_few > 0:
            self.setStatus(f"Filtered {skipped_too_few} tags without at least {min_char_count} occurrences")

        self.frame_ra.delete_all()
        self.setStatus(f"Finding potential parents for {len(orphans)} orphans")
        for char in pb_iter(self.pb, orphans):
            log_debug = self.logger.debug
            if any(substr in char for substr in self.debug_specific):
                log_debug = self.logger.warning
                log_debug(f"Triggered extra inspection for {char}")

            if self.abort_threads:
                self.abort_threads = False
                break

            si = all_relationships.get(char)
            my_counter = Counter()

            log_debug(f"No parent series for {char!r} in {si}. Searching...")

            resp = logic.client.search_files(
                tags=[char]
            )
            file_ids = resp['file_ids']
            metadata = logic.client.get_file_metadata(file_ids=file_ids)['metadata']

            for file in metadata:
                try:
                    local_display_tags = file['tags'][logic.local_tags_service_key]['display_tags']
                    if local_display_tags == {}:
                        continue

                    file_tags = local_display_tags['0']
                    my_counter.update(
                        [
                            t for t in file_tags
                            if (not parent_prefix or t.startswith(parent_prefix))
                            and t != char
                            and (not si or t not in si.ancestors)
                            and (not si or t not in si.descendants)
                        ]
                    )
                except KeyError:
                    pprint.pprint(object=file)
                    raise

            new_tags = []

            self.logger.info(f"Should we suggest adding a parent to {char} from {my_counter}?")
            if len(my_counter.keys()) == 0:
                self.logger.info("No, empty.")
                continue
            if len(my_counter.keys()) == 1:
                self.logger.info("Yes, only one option")
                new_tags = [*my_counter.keys()]
            if len(my_counter.keys()) >= 2:
                first, second, *_ = [*my_counter.keys()]
                self.logger.info(f"{first} has {my_counter[first]}, {second} has {my_counter[second]}")
                if my_counter[first] >= my_counter[second] * first_tag_factor:
                    # Actually, if the factor is 1, give options for every tie
                    new_tags = [
                        t for t in my_counter
                        if my_counter[t] == my_counter[first]
                    ]
                    self.logger.info(f"Recognizing {new_tags} as possible true parents")
                else:
                    continue

            for new_tag in new_tags:
                ra = RelationshipAction(
                    char,
                    new_tag,
                    note=", ".join(f"{t.replace(parent_prefix, '')}: {c}" for t, c in my_counter.items())
                )
                pprint.pprint(ra)
                self.frame_ra.add_item(ra)

        self.winfo_toplevel().after(10, self.frame_ra.tree_tags.resize_cols)
        self.setStatus("Done!")

if __name__ == "__main__":
    logic.init_client()
    ImplicitParentFinderWin()
