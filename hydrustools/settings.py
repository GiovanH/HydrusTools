import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from typing import Type, TypeVar

from .utils.inisettings import IniSettings

V = TypeVar("V", bound=tk.Variable)

class HTSettings(IniSettings):
    def boundTkVar(self, master, name, constructor: type[V] = tk.StringVar) -> V:
        var: V = constructor(master)

        var.set(self.__getattribute__(name))

        def onWrite(*args) -> None:
            self.__setattr__(name, var.get())

        var.trace_add("write", onWrite)

        return var

C = TypeVar('C', bound=HTSettings)

# Evil:
def settings_section(section: str | None = None, file: str = "HTSettings") -> Callable[..., HTSettings]:
    def _wrapper(cls: type[C]) -> C:
        return cls(section=section, ini_file=Path(f"{file}.ini"))

    return _wrapper
