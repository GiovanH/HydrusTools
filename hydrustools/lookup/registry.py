import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import Callable

from hydrustools.logic import FileMetadata

logger = logging.getLogger(__name__)

@dataclass()
class MetadataActions:
    file_id: int
    add_tags: None | list[str] = None
    add_downloader_tags: None | list[str] = None
    add_urls: None | list[str] = None
    add_notes: None | list[dict[str, str]] = None
    info_only: None | list[str] = None


class LookupPlugin():
    name: str
    priority: int = 10

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

def postprocessSuggestions(
    actions: MetadataActions,

    tag_namespace_whitelist: list[str] | None = None,

    tags_min_count_local: None | int = None,
    tags_min_count_download: None | int = None,
    tag_count_cache: dict[str, int] = {},

    creator_tags_always_local: bool = True,
    character_tags_always_local: bool = True,

    no_downloader_tags: bool = False,
    underscores_to_spaces: bool = False,
) -> MetadataActions:

    if actions.add_tags:
        if underscores_to_spaces:
            actions.add_tags = [
                tag.replace('_', ' ')
                for tag in actions.add_tags
            ]

        for tag_value in [*actions.add_tags]:

            # If whitelist, remove tags not matching
            if tag_namespace_whitelist:
                if not any(tag_value.startswith(f"{prefix}:") for prefix in tag_namespace_whitelist):
                    logger.debug("Removing %s, not in whitelist %s", tag_value, tag_namespace_whitelist)
                    actions.add_tags.remove(tag_value)
                    continue

            # If there's a minimum count, move tags to dltags
            if tags_min_count_local:
                # ...unless creator tags are always local
                if tag_value.startswith("creator:") and creator_tags_always_local:
                    pass
                elif tag_value.startswith("character:") and character_tags_always_local:
                    pass

                elif tag_count_cache.get(tag_value, 0) < tags_min_count_local:
                    actions.add_tags.remove(tag_value)
                    if not actions.add_downloader_tags:
                        actions.add_downloader_tags = []
                    actions.add_downloader_tags.append(tag_value)

    if actions.add_downloader_tags:
        # Remove all downloader tags?
        if no_downloader_tags:
            actions.add_downloader_tags = []

        for tag_value in [*actions.add_downloader_tags]:
            # If there's a minimum count, move tags to dltags
            if tags_min_count_download:
                if tag_count_cache.get(tag_value, 0) < tags_min_count_download:
                    actions.add_downloader_tags.remove(tag_value)
                    if not actions.info_only:
                        actions.info_only = []
                    actions.info_only.append(tag_value)

    return actions
