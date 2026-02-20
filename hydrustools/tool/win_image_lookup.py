from collections import OrderedDict
from dataclasses import dataclass
import pprint
import tkinter as tk
from tkinter import ttk
from typing import ClassVar

import hydrus_api

from hydrustools.component.HydrusImageTable import HydrusImageTable
from hydrustools.component.image_canvas import ContentCanvas
from hydrustools.component.imagetool import ImageIconSchema, ImageTool
from hydrustools.component.multicolumnlistbox import MultiColumnListbox, TreeListItemDict, TreeviewSchema
from hydrustools.settings import Settings
from hydrustools.lookup.registry import LookupPlugin, MetadataActions, postprocessSuggestions

from .. import logic
from ..logic import FileMetadata, TagInfo
from hydrustools.component.image_picker import ImageListFrame, ImagePickerWindow
from hydrustools.component.tageditorlist import TagEditorList, TagList

from ..component.gui_util import (
    Increment,
    get_selection_neighbors,
    mod_selection,
    pb_iter,
    tkwrap,
    tkwrapc,
    grooveframe
)
from ..component.toolwindow import ToolWindow

from .. import lookup

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

class ImageMetadataLookupWin(ImageTool):
    helpstr = """TODO"""
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
        self.all_relationships: dict[str, logic.SiblingInfo]

        self.listbox_taglist: TagList
        self.action_table: MultiColumnListbox

        self.pref_unknown_tags_to_dl = tk.BooleanVar(self, value=True)
        self.pref_creator_tags_always_local = tk.BooleanVar(self, value=True)
        self.pref_no_dltags = tk.BooleanVar(self, value=False)
        self.pref_replace_underscores = tk.BooleanVar(self, value=True)

        self.var_urls = tk.StringVar(self)
        self.var_id = tk.StringVar(self)
        self.var_tags = tk.StringVar(self)


        self.initwindow()
        self.bind_controls()

        self.after_idle(self.pick_images)
        self.after_idle(self.update_tag_cache)

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

            btn = ttk.Checkbutton(
                w,
                variable=self.pref_creator_tags_always_local,
                text="...except creator tags"
            ).pack(anchor='n', fill='x')
            btn = ttk.Checkbutton(
                w,
                variable=self.pref_unknown_tags_to_dl,
                text="Move unknown tags to DL, not local"
            ).pack(anchor='n', fill='x')
            btn = ttk.Checkbutton(
                w,
                variable=self.pref_no_dltags,
                text="Ignore all downloader tags"
            ).pack(anchor='n', fill='x')
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

            with tkwrapc(ttk.Frame(master=window)) as (left_frame, cx, cy):
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

    def set_image(self, metadata: logic.FileMetadata):
        refreshing = False
        if self.current_image and metadata['file_id'] == self.current_image.get('file_id'):
            refreshing = True

        super().set_image(metadata)

        if not refreshing:
            self.action_table.delete_all()

        assert self.current_image

        tag_list = logic.local_tags(self.current_image)

        self.var_id.set(str(self.current_image['file_id']))
        self.var_urls.set('\n'.join(self.current_image['known_urls']))

        self.listbox_taglist.delete(0, self.listbox_taglist.size())

        for tag in logic.sort_tags(tag_list):
            self.listbox_taglist.insert(tk.END, tag)

        for (id_, var) in self.plugin_enabled.items():
            if plugin_registry[id_].match(self.current_image):
                self.checkbuttons[id_].config(state=tk.NORMAL)
            else:
                self.checkbuttons[id_].config(state=tk.DISABLED)

        self.setStatus(f"Selected image {self.current_image['file_id']}")

    def runPlugin(self, plugin_id):
        assert self.current_image
        plugin = plugin_registry[plugin_id]
        actions = plugin.suggest(self.current_image, setStatus=self.setStatus)

        if not actions:
            return

        self.addSuggestions(plugin, actions)

    def update_tag_cache(self):
        all_tags = logic.search_tags_re("*", subpattern=None)
        all_tags_set = {ti.value for ti in all_tags}
        self.tag_count_cache = {ti.value: ti.count for ti in all_tags}

        sibling_resp = logic.get_sibling_ideal_targets([*all_tags_set])
        self.all_relationships: dict[str, logic.SiblingInfo] = {
            **{
                s: si
                for si in
                sibling_resp
                for s in si.siblings
            }
        }

    def addSuggestions(self, plugin: LookupPlugin, actions: MetadataActions):
        assert self.current_image

        min_tag_count = (10 if self.pref_unknown_tags_to_dl.get() else None)
        actions = postprocessSuggestions(
            actions,

            unknown_tags_min_count=min_tag_count,
            tag_count_cache=self.tag_count_cache,

            no_downloader_tags=self.pref_no_dltags.get(),
            underscores_to_spaces=self.pref_replace_underscores.get(),

            creator_tags_always_local=self.pref_creator_tags_always_local.get()
        )

        for url in actions.add_urls or []:
            if url in self.current_image['known_urls']:
                continue

            self.action_table.insert_item(MetadataActionSchema.to_tree_item(MetadataActionViz(
                file_id=actions.file_id,
                source=plugin.name,
                property="URL",
                value=url,
                context=""
            )))

        for tag_value in actions.add_tags or []:
            # TODO: Siblings
            if tag_value in logic.local_tags(self.current_image):
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
            if tag_value in logic.local_tags(self.current_image):
                continue

            # TODO: Siblings
            context = f"{self.tag_count_cache.get(tag_value, 0)}"

            self.action_table.insert_item(MetadataActionSchema.to_tree_item(MetadataActionViz(
                file_id=actions.file_id,
                source=plugin.name,
                property="Downloader Tag",
                value=tag_value,
                context=context
            )))


        if actions.add_notes:
            self.setStatus("Not implemented: add_notes")

    def doSearch(self, event=None):
        if not self.current_image:
            self.setStatus("Can't run lookup with no image selected")
            return

        self.action_table.delete_all()

        for (id_, var) in pb_iter(self.pb, [*self.plugin_enabled.items()]):
            if var.get():
                self.runPlugin(id_)

        self.after_idle(self.action_table.resize_cols)

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

        for values in items:
            if int(values['file_id']) != file_id:
                raise ValueError("Sanity check failed: Tried to apply action %s to file %s" % (values, file_id))
            if values['property'] == 'Tag':
                all_tags.append(values['value'])
            elif values['property'] == 'Downloader Tag':
                all_tags.append(values['value'])
            elif values['property'] == 'URL':
                all_urls.append(values['value'])
            else:
                raise NotImplementedError(values['property'])

        pprint.pprint([all_tags, all_urls])

        acted = False

        if len(all_downloader_tags) > 0:
            self.setStatus(f"Adding {len(all_downloader_tags)} tags")
            logic.client.add_tags(
                file_ids=[file_id],
                service_keys_to_tags={
                    logic.downloader_tags_service_key: all_downloader_tags
                }
            )
            acted = True

        if len(all_tags) > 0:
            self.setStatus(f"Adding {len(all_tags)} tags")
            logic.client.add_tags(
                file_ids=[file_id],
                service_keys_to_tags={
                    logic.local_tags_service_key: all_tags
                }
            )
            acted = True

        if len(all_urls) > 0:
            self.setStatus(f"Adding {len(all_urls)} source urls")
            logic.client.associate_url(file_ids=[file_id], urls_to_add=all_urls)
            acted = True

        if acted:
            self.refresh_current()