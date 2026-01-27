from .inisettings import IniSettings

import tkinter as tk
import hydrus_api
from typing import TypeVar, Type

V = TypeVar("V", bound=tk.Variable)

class HTSettings(IniSettings):
    hydrus_api_key: str = "CHANGEME"
    hydrus_api_url: str = hydrus_api.DEFAULT_API_URL

    flatten_presearch: str = "<Changeme>"
    flatten_search: str = ""

    note_notename: str = "filename"
    note_pattern: str = ""
    note_partial: bool = False

    def boundTkVar(self, master, name: str, constructor: Type[V] = tk.StringVar) -> V:
        var: V = constructor(master)

        var.set(self.__getattribute__(name))
        def onWrite(*args) -> None:
            self.__setattr__(name, var.get())

        var.trace_add('write', onWrite)

        return var

if __name__ == "__main__":
    settings = HTSettings()

    print(settings.note_notename)
    print(settings.note_pattern)

