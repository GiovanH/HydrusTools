from .inisettings import IniSettings

import tkinter as tk
import hydrus_api
from typing import TypeVar, Type

V = TypeVar("V", bound=tk.Variable)

class HTSettings(IniSettings):
    hydrus_api_key: str = "CHANGEME"
    hydrus_api_url: str = hydrus_api.DEFAULT_API_URL

    gui_last: int = -1

    flatten_presearch: str = "<Changeme>"
    flatten_search: str = ""

    tagsearch_presearch: str = "<Changeme>"
    tagsearch_search: str = ""
    tagsearch_presearch_hist: str = ""
    tagsearch_search_hist: str = ""
    tagsearch_localonly: bool = True

    note_prequery: str = ""
    note_notename: str = "filename"
    note_pattern: str = ""
    note_partial: bool = False

    findimplicitparent_ns_parent: str = "series:"
    findimplicitparent_ns_child: str = "character:"
    findimplicitparent_min_count: int = 2
    findimplicitparent_factor: int = 2

    extractcreatornote_search: str = ""
    extractcreatornote_search_hist: str = ""
    extractcreatornote_notename: str = "filename"
    extractcreatornote_min_count: int = 2

    imagesearch_query: str = ""
    imagesearch_query_hist: str = ""

    def boundTkVar(self, master, name, constructor: Type[V] = tk.StringVar) -> V:
        var: V = constructor(master)

        var.set(self.__getattribute__(name))

        def onWrite(*args) -> None:
            self.__setattr__(name, var.get())

        var.trace_add("write", onWrite)

        return var

Settings = HTSettings()

if __name__ == "__main__":
    settings = HTSettings()

    print(settings.note_notename)
    print(settings.note_pattern)
