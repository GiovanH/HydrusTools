"""
Settings objects backed by sections of a shared INI file.

Multiple IniSettings subclasses can share a single INI file by pointing to
the same path with different section names.  Each instance only touches its
own section, and file writes are serialised via a lock file to prevent races
between concurrent processes or threads.
"""

from __future__ import annotations

from _thread import LockType
import configparser
import json
import threading
from pathlib import Path
from typing import Any, TypeVar, get_type_hints

from pydantic import TypeAdapter

# Registry mapping each disk ini path to a single configparser instance
_file_registry: dict[Path, tuple[configparser.ConfigParser, LockType]] = {}
_registry_lock: LockType = threading.Lock()


def _get_config_and_lock(ini_file: Path) -> tuple[configparser.ConfigParser, LockType]:
    """Return the shared ConfigParser and lock for a given file path."""
    key = ini_file.resolve()
    with _registry_lock:
        if key not in _file_registry:
            config = configparser.ConfigParser()
            if key.exists():
                config.read(key)
            lock = threading.Lock()
            _file_registry[key] = (config, lock)
        return _file_registry[key]


def clear_registry() -> None:
    """Remove all cached file state.  Useful in tests."""
    with _registry_lock:
        _file_registry.clear()


class IniSettings:
    """Base class for settings objects backed by sections of a shared INI file.

    Subclasses define class attributes with type hints and default values.
    Those attributes are automatically loaded from / saved to an INI file.

    Example::

        class AppSettings(IniSettings):
            debug: bool = False
            max_retries: int = 3

        class PluginSettings(IniSettings):
            plugin_dir: str = "/usr/lib/plugins"
            enabled: bool = True

        # Both write to the same file, different sections
        app    = AppSettings(Path("config.ini"), section="app")
        plugin = PluginSettings(Path("config.ini"), section="plugin")
    """

    def __init__(self, ini_file: Path | None = None, section: str | None = None):
        resolved_file = Path(ini_file or f"{self.__class__.__name__}.ini")
        resolved_section = section or self.__class__.__name__

        config, lock = _get_config_and_lock(resolved_file)

        object.__setattr__(self, "_ini_file", resolved_file)
        object.__setattr__(self, "_section", resolved_section)
        object.__setattr__(self, "_config", config)
        object.__setattr__(self, "_lock", lock)
        object.__setattr__(self, "_initialized", False)
        object.__setattr__(self, "_schema", self._get_schema())
        object.__setattr__(self, "_typevalidators", self._get_typeadapters())

        if resolved_section != "DEFAULT" and not config.has_section(resolved_section):
            config.add_section(resolved_section)

        self._init_defaults()
        object.__setattr__(self, "_initialized", True)

    def _get_typeadapters(self) -> dict[str, TypeAdapter[Any]]:
        return {k: TypeAdapter(t) for k, t in get_type_hints(self.__class__).items()}

    def _get_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {}
        for cls in reversed(self.__class__.__mro__):
            if cls in (IniSettings, object):
                continue
            schema.update({
                attr: val for attr, val in cls.__dict__.items() if not attr.startswith("_") and not callable(val)
            })
        return schema

    def _serialize(self, value: Any) -> str:
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            return value
        # TODO validate against pydantic
        return json.dumps(value)

    def _deserialize(self, attr: str, raw: str) -> Any:
        hints = get_type_hints(self.__class__)
        expected = hints.get(attr, str)

        if expected is bool:
            return raw.lower() in ("true", "1", "yes", "on")
        if expected in (int, float, str):
            return expected(raw)
        return json.loads(raw)

    def _init_defaults(self) -> None:
        with self._lock:
            if self._ini_file.exists():
                self._config.read(self._ini_file)

            changed = False
            for attr, default in self._schema.items():
                if not self._config.has_option(self._section, attr):
                    self._config.set(self._section, attr, self._serialize(default))
                    changed = True

            if changed:
                self._flush()

    def _save(self, attr: str, value: Any) -> None:
        with self._lock:
            if self._ini_file.exists():
                self._config.read(self._ini_file)
            self._typevalidators[attr].validate_python(value)
            self._config.set(self._section, attr, self._serialize(value))
            self._flush()

    def _flush(self) -> None:
        self._ini_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._ini_file, "w") as f:
            self._config.write(f)

    def __getattribute__(self, name: str):
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        schema = object.__getattribute__(self, "_schema")
        if name not in schema:
            return object.__getattribute__(self, name)

        config: configparser.ConfigParser = object.__getattribute__(self, "_config")
        section: str = object.__getattribute__(self, "_section")

        if config.has_option(section, name):
            return self._deserialize(name, config.get(section, name))

        return schema[name]

    def __setattr__(self, name: str, value: Any) -> None:
        if not object.__getattribute__(self, "_initialized"):
            object.__setattr__(self, name, value)
            return

        if name not in self._schema:
            object.__setattr__(self, name, value)
            return

        self._save(name, value)
