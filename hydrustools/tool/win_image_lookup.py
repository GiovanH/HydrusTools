import tkinter as tk
from collections import OrderedDict
from dataclasses import dataclass
from tkinter import ttk
from typing import ClassVar

from hydrustools.component.imagetool import ImageIconSchema, ImageTool
from hydrustools.component.multicolumnlistbox import MultiColumnListbox, TreeListItemDict, TreeviewSchema
from hydrustools.component.tag_list_editor import TagList
from hydrustools.lookup.registry import LookupPlugin, MetadataActions, postprocessSuggestions
import hydrustools.utils.namespace

from .. import lookup
from ..utils import hydrus
from ..utils.gui_util import (
    grooveframe,
    pb_iter,
    tkwrap,
    tkwrapc,
)

plugin_registry: dict[str, LookupPlugin] = None # type: ignore

class ImageIconSchemaBig(ImageIconSchema):
    imagesize = (180, 180)

@dataclass()
class MetadataActionViz:
    file_id: int
    source: str
    property: str
    value: str
    context: str = ""

class MetadataActionSchema(TreeviewSchema[MetadataActionViz]):
    headers: ClassVar[OrderedDict[str, str | None]] = OrderedDict([
        ('file_id', None),
        ('source', "Source"),
        ('property', "Property"),
        ('value', "Value"),
        ('context', "Context"),
    ])

    @staticmethod
    def to_tree_item(item: MetadataActionViz) -> TreeListItemDict:
        return {
            "values": [item.file_id, item.source, item.property, item.value, item.context]
        }

PROP_LOCAL_TAG = "Tag"
PROP_DOWNLOADER_TAG = "Downloader Tag"
PROP_URL = "URL"
PROP_INFO_ONLY = "Disabled"

class ImageMetadataLookupWin(ImageTool):
    label = "Image Metadata Lookup"
    helpstr = """Similar to the Image Inspector, but looks up image metadata based on lookup plugins.

Heavy work-in-progress"""
    schema = ImageIconSchemaBig
    def __init__(self, *args_, **kwargs) -> None:
        super().__init__(*args_, **kwargs)


        global plugin_registry
        plugin_registry = lookup.registry.get_plugins()

        self.get_file_metadata_kwargs = {
            "include_notes": True,
            "detailed_url_information": True
        }

        self.plugin_enabled = {
            name: tk.BooleanVar(self, value=True)
            for name in plugin_registry.keys()
        }
        self.checkbuttons: dict[str, ttk.Checkbutton] = {}

        self.tag_count_cache: dict[str, int] = {}
        self.all_relationships: dict[str, hydrus.RelationshipInfo]

        self.listbox_taglist: TagList
        self.action_table: MultiColumnListbox

        # self.pref_unknown_tags_to_dl = tk.BooleanVar(self, value=True)
        self.pref_min_count_local = tk.IntVar(self, value=20)
        self.pref_min_count_download = tk.IntVar(self, value=1)
        self.pref_creator_tags_always_local = tk.BooleanVar(self, value=True)
        self.pref_character_tags_always_local = tk.BooleanVar(self, value=True)
        self.pref_no_dltags = tk.BooleanVar(self, value=False)
        self.pref_replace_underscores = tk.BooleanVar(self, value=True)

        self.var_urls = tk.StringVar(self)
        self.var_id = tk.StringVar(self)
        self.var_tags = tk.StringVar(self)

        self.pref_autosearch: tk.BooleanVar = tk.BooleanVar(self, value=False)

        self.initwindow()
        self.bind_controls()

        self.after_idle(self.pick_images)
        self.startTask(self.update_tag_cache, lock=False)
        self.bind('<F5>', self.update_tag_cache)

        self.mainloop()

    def initwindow(self):
        self.title("Image Search")
        self.geometry("1200x675")

        def col_current(m):
            w = grooveframe(m)
            ttk.Label(
                w,
                text="Current Metadata",
            ).pack(anchor='n', fill='x')

            ttk.Label(
                w,
                textvariable=self.var_id
            ).pack(anchor='n', fill='x')

            ttk.Label(
                w,
                textvariable=self.var_urls
            ).pack(anchor='n', fill='x')

            self.listbox_taglist = TagList(w)
            self.listbox_taglist.pack(anchor='n', fill=tk.BOTH, expand=True)
            return w

        def col_plugins(m):
            w = grooveframe(m)
            ttk.Label(
                w,
                text="Prefs",
            ).pack(anchor='n', fill='x')

            with tkwrap(ttk.Frame(w)) as frame:
                ttk.Label(frame, text="Min count for local").pack(anchor='w')
                ttk.Spinbox(frame, textvariable=self.pref_min_count_local, from_=0, to=500).pack(anchor='e')

                frame.pack(anchor='n', fill='x')

            with tkwrap(ttk.Frame(w)) as frame:
                ttk.Label(frame, text="Min count for download").pack(anchor='w')
                ttk.Spinbox(frame, textvariable=self.pref_min_count_download, from_=0, to=500).pack(anchor='e')

                frame.pack(anchor='n', fill='x')

            btn = ttk.Checkbutton(
                w,
                variable=self.pref_creator_tags_always_local,
                text="Creator tags always local"
            ).pack(anchor='n', fill='x')

            btn = ttk.Checkbutton(
                w,
                variable=self.pref_character_tags_always_local,
                text="Character tags always local"
            ).pack(anchor='n', fill='x')

            # btn = ttk.Checkbutton(
            #     w,
            #     variable=self.pref_no_dltags,
            #     text="Ignore all downloader tags"
            # ).pack(anchor='n', fill='x')
            btn = ttk.Checkbutton(
                w,
                variable=self.pref_replace_underscores,
                text="Replace underscores with spaces"
            ).pack(anchor='n', fill='x')

            ttk.Label(
                w,
                text="Plugins",
            ).pack(anchor='n', fill='x')


            for (id_, var) in self.plugin_enabled.items():
                label = plugin_registry[id_].name
                btn = ttk.Checkbutton(
                    w,
                    variable=var,
                    text=label
                )
                self.checkbuttons[id_] = btn
                btn.pack(anchor='n', fill='x')

            btn_refresh = ttk.Button(w, text="Lookup", command=self.startTaskCurry(self.doSearch))
            btn_refresh.pack(anchor='s', fill='x')

            btn = ttk.Checkbutton(
                w,
                variable=self.pref_autosearch,
                text="Automatically lookup"
            ).pack(anchor='n', fill='x')

            btn_refresh = ttk.Button(w, text="Apply All to All", command=self.applyAll)
            btn_refresh.pack(side=tk.BOTTOM, fill='x')
            return w



        def col_suggestions(m):
            w = grooveframe(m)
            ttk.Label(
                w,
                text="Suggestions"
            ).pack(anchor='n', fill='x')

            self.action_table = MultiColumnListbox(w, schema=MetadataActionSchema)
            self.action_table.pack(anchor='n', fill=tk.BOTH, expand=True)

            with tkwrap(ttk.Frame(w)) as frame:
                btn_selected = ttk.Button(frame, text="Apply selected", command=self.apply_selected, width=30)
                btn_selected.pack(side=tk.RIGHT)
                btn_all = ttk.Button(frame, text="Apply all", command=self.apply_all, width=30)
                btn_all.pack(side=tk.RIGHT)

                frame.pack(side=tk.BOTTOM, fill=tk.X)

            with tkwrap(ttk.Frame(w)) as frame:
                btn_selected = ttk.Button(frame, text="Set selected to Local", command=lambda *e: self.edit_selected_property(PROP_LOCAL_TAG)).pack(side=tk.RIGHT)
                btn_selected = ttk.Button(frame, text="Set selected to Download Tag", command=lambda *e: self.edit_selected_property(PROP_DOWNLOADER_TAG)).pack(side=tk.RIGHT)

                frame.pack(side=tk.BOTTOM, fill=tk.X)

            return w

        def row_status(m):
            w = grooveframe(m)

            self.pb = ttk.Progressbar(w, orient='vertical',
                mode='determinate',
                length=30
            )
            self.pb.pack(side=tk.LEFT, fill=tk.Y)

            ttk.Label(w, textvariable=self.textvar_status).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            return w


        with tkwrap(ttk.PanedWindow(self, orient="horizontal")) as window:
            window.pack(expand=True, fill=tk.BOTH)

            with tkwrapc(ttk.Frame(master=window)) as (left_frame, cx, _):
                # Fixed-width image frame
                self.fac_image_list_frame(left_frame).grid(column=cx.inc(), row=0, sticky="ns")

                left_frame.rowconfigure(index=0, weight=1)
                # Stretchy editor columns
                with tkwrap(ttk.PanedWindow(left_frame, orient="horizontal")) as frame:
                    frame.add(col_current(frame), weight=1)
                    frame.add(col_plugins(frame), weight=1)

                    frame.grid(column=cx.inc(), row=0, sticky="nsew")
                    left_frame.columnconfigure(index=cx.value, weight=1)

                # Columnspan status bar
                row_status(left_frame).grid(column=0, row=1, columnspan=cx.inc(), sticky="nsew")

                window.add(left_frame, weight=2)

            window.add(col_suggestions(window), weight=3)

        self.image_list.resize_cols()



    def bind_controls(self):
        pass

    def set_image(self, metadata: hydrus.FileMetadata):
        refreshing = False
        if self.current_image and metadata['file_id'] == self.current_image.get('file_id'):
            refreshing = True

        super().set_image(metadata)

        if not refreshing:
            self.action_table.delete_all()

        assert self.current_image

        tag_list = hydrus.local_tags(self.current_image)

        self.var_id.set(str(self.current_image['file_id']))
        self.var_urls.set('\n'.join(self.current_image['known_urls']))

        self.listbox_taglist.delete(0, self.listbox_taglist.size())

        for tag in hydrustools.utils.namespace.sort_tags(tag_list):
            self.listbox_taglist.insert(tk.END, tag)

        for (id_, var) in self.plugin_enabled.items():
            if plugin_registry[id_].match(self.current_image):
                self.checkbuttons[id_].config(state=tk.NORMAL)
            else:
                self.checkbuttons[id_].config(state=tk.DISABLED)

        self.setStatus(f"Selected image {self.current_image['file_id']}")
        # traceback.print_stack()

        if self.pref_autosearch.get():
            self.startTask(self.doSearch)

    def runPlugin(self, plugin_id):
        assert self.current_image
        plugin = plugin_registry[plugin_id]
        actions = plugin.suggest(self.current_image, setStatus=self.setStatus)

        if not actions:
            return

        self.addSuggestions(plugin, actions)

    def update_tag_cache(self, event=None):
        if event:
            self.setStatus("Updating tag cache...")

        all_tags = hydrus.search_tags_re("*", subpattern=None)
        all_tags_set = {ti.value for ti in all_tags}
        self.tag_count_cache = {ti.value: ti.count for ti in all_tags}

        sibling_resp = hydrus.get_relationship_info([*all_tags_set])
        self.all_relationships: dict[str, hydrus.RelationshipInfo] = {
            **{
                s: si
                for si in
                sibling_resp
                for s in si.siblings
            }
        }

        for tag, si in self.all_relationships.items():
            ideal = si.ideal_tag

            # Quick and dirty, not completely accurate
            # Would need to loop multiple times and make sure each sibling group shared a pool, etc
            if self.tag_count_cache.get(ideal) != self.tag_count_cache.get(tag):
                total = self.tag_count_cache.get(ideal, 0) + self.tag_count_cache.get(tag, 0)
                self.tag_count_cache[tag] = total
                self.tag_count_cache[ideal] = total

        if event:
            self.setStatus("Updated tag cache.")

    def addSuggestions(self, plugin: LookupPlugin, actions: MetadataActions):
        assert self.current_image

        # TODO configurability
        always_local_namespaces = [
            'title', 'series', 'rating'
        ]

        if self.pref_character_tags_always_local.get():
            always_local_namespaces.append('character')
        if self.pref_creator_tags_always_local.get():
            always_local_namespaces.append('creator')

        actions = postprocessSuggestions(
            actions,

            tags_min_count_local=self.pref_min_count_local.get(),
            tags_min_count_download=self.pref_min_count_download.get(),
            tag_count_cache=self.tag_count_cache,

            # no_downloader_tags=self.pref_no_dltags.get(),
            underscores_to_spaces=self.pref_replace_underscores.get(),

            always_local_namespaces=always_local_namespaces,
        )

        for url in actions.add_urls or []:
            # Cheap emulation of credential stripping
            if any(url.startswith(known) for known in self.current_image['known_urls']):
                continue

            self.action_table.insert_item(MetadataActionSchema.to_tree_item(MetadataActionViz(
                file_id=actions.file_id,
                source=plugin.name,
                property=PROP_URL,
                value=url,
                context=""
            )))

        for tag_value in actions.add_tags or []:

            if tag_value in hydrus.local_tags(self.current_image):
                continue
            if tag_value in self.all_relationships and self.all_relationships[tag_value].ideal_tag in hydrus.local_tags(self.current_image):
                continue

            # TODO: Siblings
            context = f"{self.tag_count_cache.get(tag_value, 0)}"

            self.action_table.insert_item(MetadataActionSchema.to_tree_item(MetadataActionViz(
                file_id=actions.file_id,
                source=plugin.name,
                property="Tag",
                value=tag_value,
                context=context
            )))

        for tag_value in actions.add_downloader_tags or []:
            # TODO: Siblings
            if tag_value in hydrus.local_tags(self.current_image):
                continue

            # TODO: Siblings
            context = f"{self.tag_count_cache.get(tag_value, 0)}"

            self.action_table.insert_item(MetadataActionSchema.to_tree_item(MetadataActionViz(
                file_id=actions.file_id,
                source=plugin.name,
                property=PROP_DOWNLOADER_TAG,
                value=tag_value,
                context=context
            )))


        for tag_value in actions.info_only or []:
            # TODO: Siblings
            context = f"{self.tag_count_cache.get(tag_value, 0)}"

            self.action_table.insert_item(MetadataActionSchema.to_tree_item(MetadataActionViz(
                file_id=actions.file_id,
                source=plugin.name,
                property=PROP_INFO_ONLY,
                value=tag_value,
                context=context
            )))


        if actions.add_notes:
            self.setStatus("Not implemented: add_notes")

    def applyAll(self, event=None):
        cur_selection: tuple[str, ...] = self.image_list.tree.selection()
        prev_selection: tuple[str, ...] = ()

        while (cur_selection != prev_selection):
            if self.abort_threads:
                self.setStatus("Aborted!")
                return

            self.setStatus(f"Applying next in list, {cur_selection} != {prev_selection}")

            # if len(self.action_table.tree.get_children()) == 0:
            self.doSearch()
            self.update()

            self.apply_all()
            self.update()

            self.logger.info("Applied all, now incrementing")

            prev_selection = self.image_list.tree.selection()
            prev_autosearch = self.pref_autosearch.get()
            self.pref_autosearch.set(False)
            self.next_image()
            self.update()
            cur_selection = self.image_list.tree.selection()
            self.pref_autosearch.set(prev_autosearch)

            self.logger.info("Incremented, now looping")
        self.setStatus("Done!")

    def doSearch(self, event=None):
        if not self.current_image:
            self.setStatus("Can't run lookup with no image selected")
            return

        self.action_table.delete_all()

        for (id_, var) in pb_iter(self.pb, [*self.plugin_enabled.items()]):
            if var.get():
                self.setStatus(f"Running {id_}")
                self.runPlugin(id_)

        self.after_idle(self.action_table.resize_cols)


    def edit_selected_property(self, property: str):
        for tkid in self.action_table.tree.selection():
            self.action_table.tree.set(tkid, column="property", value=property)

    def apply_selected(self):
        self.apply_items(self.action_table.getSelectionDicts())
        self.action_table.tree.delete(*self.action_table.tree.selection())

    def apply_all(self):
        self.apply_items(self.action_table.getAllDicts())
        self.action_table.delete_all()

    def apply_items(self, items: list[dict]):
        assert self.current_image

        file_id = self.current_image['file_id']

        all_urls = []
        all_tags = []
        all_downloader_tags = []

        self.setStatus(f"Applying {len(items)} actions to image {file_id}")

        for values in items:
            if int(values['file_id']) != file_id:
                raise ValueError("Sanity check failed: Tried to apply action %s to file %s" % (values, file_id))
            if values['property'] == PROP_LOCAL_TAG:
                all_tags.append(values['value'])
            elif values['property'] == PROP_DOWNLOADER_TAG:
                all_downloader_tags.append(values['value'])
            elif values['property'] == PROP_URL:
                all_urls.append(values['value'])
            elif values['property'] == PROP_INFO_ONLY:
                pass
            else:
                raise NotImplementedError(values['property'])

        acted = False

        if len(all_downloader_tags) > 0:
            self.setStatus(f"Adding {len(all_downloader_tags)} tags")
            hydrus.client.add_tags(
                file_ids=[file_id],
                service_keys_to_tags={
                    hydrus.downloader_tags_service_key: all_downloader_tags
                }
            )
            acted = True

        if len(all_tags) > 0:
            self.setStatus(f"Adding {len(all_tags)} tags")
            hydrus.client.add_tags(
                file_ids=[file_id],
                service_keys_to_tags={
                    hydrus.local_tags_service_key: all_tags
                }
            )
            acted = True

        if len(all_urls) > 0:
            self.setStatus(f"Adding {len(all_urls)} source urls")
            hydrus.client.associate_url(file_ids=[file_id], urls_to_add=all_urls)
            acted = True

        if acted:
            self.after_idle(self.refresh_current)