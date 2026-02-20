import configparser
import json
from pathlib import Path
from typing import Any, get_type_hints, get_origin


class IniSettings:
    """Base class for settings objects backed by persistent INI files.

    Subclasses should define class attributes with type hints and default values.
    These attributes will be automatically loaded from/saved to an INI file.

    Example:
        class MySettings(IniSettings):
            username: str = "default_user"
            max_connections: int = 10
            enabled: bool = True
            timeout: float = 30.5
    """

    _ini_file: Path
    _config: configparser.ConfigParser
    _section: str = "DEFAULT"
    _list_delimiter: str = "|"
    _initialized: bool = False

    _schema: dict[str, Any]

    def __init__(self, ini_file: Path | None = None, section: str = "DEFAULT"):
        """Initialize settings from an INI file.

        Args:
            ini_file: Path to the INI file (created if it doesn't exist)
            section: INI section name to use for storing settings
        """
        # Store instance variables without triggering __setattr__
        object.__setattr__(self, "_ini_file", Path(ini_file or f"{self.__class__.__name__}.ini"))
        object.__setattr__(self, "_section", section)
        object.__setattr__(self, "_config", configparser.ConfigParser())
        object.__setattr__(self, "_initialized", False)
        object.__setattr__(self, "_schema", self._get_schema())

        # Load existing INI file if it exists
        if self._ini_file.exists():
            self._config.read(self._ini_file)

        # Ensure section exists
        if not self._config.has_section(self._section) and self._section != "DEFAULT":
            self._config.add_section(self._section)

        # Initialize with defaults for any missing values
        self._init_defaults()

        object.__setattr__(self, "_initialized", True)

    def _init_defaults(self):
        """Initialize settings with default values if not present in INI."""
        schema = self._schema
        changed = False

        for attr, default_value in schema.items():
            if not self._config.has_option(self._section, attr):
                self._config.set(self._section, attr, self._serialize(default_value))
                changed = True

        if changed:
            self._save()

    def _get_schema(self) -> dict[str, Any]:
        """Get the schema (class attributes with defaults) for this settings class."""
        schema = {}

        # Iterate through the class hierarchy to get all defaults
        for cls in reversed(self.__class__.__mro__):
            if cls is IniSettings or cls is object:
                continue

            # Get class attributes that have defaults
            for attr, default in cls.__dict__.items():
                if not attr.startswith("_") and not callable(default):
                    schema[attr] = default

        return schema

    def _serialize(self, value: Any) -> str:
        """Convert a Python value to a string for INI storage."""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            return str(value)
        return json.dumps(value)

    def _deserialize(self, attr: str, value: str) -> Any:
        """Convert an INI string value to the appropriate Python type."""
        type_hints = get_type_hints(self.__class__)
        expected_type = type_hints.get(attr, str)

        # Handle boolean specially
        if expected_type is bool:
            return value.lower() in ("true", "1", "yes", "on")

        # Handle other basic types
        if expected_type in (int, float, str):
            return expected_type(value)

        return json.loads(value)

    def _save(self) -> None:
        """Save the current configuration to the INI file."""
        self._ini_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._ini_file, "w") as f:
            self._config.write(f)

    def __getattribute__(self, name: str) -> Any:
        """Intercept attribute access to load from INI file."""
        # Allow access to private attributes and methods normally
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        # Check if this is part of the schema
        if name not in self._schema:
            return object.__getattribute__(self, name)

        # Load from INI
        config = self._config
        section = self._section

        if config.has_option(section, name):
            raw_value = config.get(section, name)
            deserialize = self._deserialize
            return deserialize(name, raw_value)

        # Return default if not in INI
        return self._schema[name]

    def __setattr__(self, name: str, value: Any):
        """Intercept attribute writes to save to INI file."""
        # Before initialization, use normal attribute setting
        if not object.__getattribute__(self, "_initialized"):
            object.__setattr__(self, name, value)
            return

        # Check if this is part of the schema
        if name not in self._schema:
            object.__setattr__(self, name, value)
            return

        # Save to INI
        self._config.set(self._section, name, self._serialize(value))
        self._save()
