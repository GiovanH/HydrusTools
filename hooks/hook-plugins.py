from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("hydrustools.lookup")

import pkgutil
import hydrustools.lookup
from pathlib import Path

names = [name for _, name, _ in pkgutil.iter_modules(hydrustools.lookup.__path__)]
out = Path("hydrustools/lookup/_modules.py")
out.write_text(f"__all__ = {names!r}\n")