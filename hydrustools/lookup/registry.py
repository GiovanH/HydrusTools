from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable

from hydrustools.logic import FileMetadata

@dataclass()
class MetadataActions:
    file_id: int
    add_tags: None | list[str] = None
    add_downloader_tags: None | list[str] = None
    add_urls: None | list[str] = None
    add_notes: None | list[dict[str, str]] = None


class LookupPlugin():
    name: str

    @abstractmethod
    def match(self, metadata: FileMetadata) -> bool:
        """Determine whether this plugin is applicable to a given file.

        Returns:
            bool: True if this plugin can provide information about the file, else False
        """
        pass

    @abstractmethod
    def suggest(self, metadata: FileMetadata, setStatus: Callable[[str], None]) -> MetadataActions | None:
        pass


_registry: dict[str, type[LookupPlugin]] = {}

def register(cls: type[LookupPlugin]):
    name = f"{cls.__module__}.{cls.__qualname__}"
    _registry[name] = cls
    return cls

def get_plugins() -> dict[str, LookupPlugin]:
    return {
        plugin_id: plugin()
        for plugin_id, plugin in _registry.items()
    }