import logging
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from hydrustools.settings import HTSettings, settings_section
from hydrustools.utils import hydrus
from hydrustools.utils.hydrus import FileMetadata

logger = logging.getLogger(__name__)

PRIOR_BY_URL = 10
PRIOR_BY_HASH = 5

@settings_section(section="Lookup", file="Lookup")
class LookupSettings(HTSettings):
    min_count_local: int | None = None
    min_count_download: int | None = 1
    underscores_to_spaces: bool = True
    blacklist_tags_from_local: list[str] = []
    tag_namespace_whitelist: list[str] = []
    always_local_namespaces: list[str] = [
        'creator',
        'character',
        'title',
        'series',
        'rating'
    ]


@dataclass()
class MetadataActions:
    file_id: int
    add_tags: list[str] = field(default_factory=list)
    add_downloader_tags: list[str] = field(default_factory=list)
    add_urls: list[str] = field(default_factory=list)
    add_notes: list[dict[str, str]] = field(default_factory=list)
    info_only: list[str] = field(default_factory=list)
    source: 'LookupPlugin | None' = None

    def has_any(self):
        for list_ in [
            self.add_tags,
            self.add_downloader_tags,
            self.add_urls,
            self.add_notes,
            self.info_only
        ]:
            if list_ and len(list_) > 0:
                return True
        return False

    def remaining_for(self, image: FileMetadata) -> 'MetadataActions':
        if self.file_id != image['file_id']:
            raise ValueError(f"MetadataActions {self} attempted to check image with mismatching id {image['file_id']}")

        def set_subtract(a: list[str] | None, b: list[str]) -> list[str] | None:
            return [*(
                set(a or []) - set(b)
            )] or None

        merged = {
            **asdict(self),
            # file_id=self.file_id,
            # add_notes=self.add_notes,
            # info_only=self.info_only,
            # source=self.source,
            "add_tags": set_subtract(
                self.add_tags,
                hydrus.local_tags(image)
            ),
            "add_downloader_tags": set_subtract(
                self.add_downloader_tags,
                hydrus.local_tags(image, service_key=hydrus.downloader_tags_service_key)
            ),
            "add_urls": set_subtract(
                self.add_urls,
                image['known_urls']
            )
        }

        return MetadataActions(**merged) # type: ignore

class LookupPlugin():
    name: str
    priority: int = 10  # Lower numbers go first
    default_enabled: bool = True

    @abstractmethod
    def match(self, metadata: FileMetadata) -> bool:
        """Determine whether this plugin is applicable to a given file.

        Returns:
            bool: True if this plugin can provide information about the file, else False
        """

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

    tags_min_count_local: None | int = 0,
    tags_min_count_download: None | int = 0,
    tag_count_cache: dict[str, int] = {},

    always_local_namespaces: list[str] = [],

    blacklist_tags_from_local: list[str] = [],

    # no_downloader_tags: bool = False,
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

            # ...unless creator tags are always local
            never_downgrade = False
            for ns in always_local_namespaces:
                if tag_value.startswith(f"{ns}:"):
                    never_downgrade = True
            if never_downgrade:
                continue

            # Downgrade because...?
            dg_bc_list: bool = tag_value in blacklist_tags_from_local
            dg_bc_threshhold: bool = tag_count_cache.get(tag_value, 0) < tags_min_count_local if tags_min_count_local else False
            dg_bc_none = (tags_min_count_local is None)

            if dg_bc_threshhold or dg_bc_list or dg_bc_none:
                actions.add_tags.remove(tag_value)
                # if not actions.add_downloader_tags:
                #     actions.add_downloader_tags = []
                actions.add_downloader_tags.append(tag_value)

    if actions.add_downloader_tags:

        for tag_value in [*actions.add_downloader_tags]:
            # If there's a minimum count, move tags to dltags
            dg_bc_threshhold: bool = tag_count_cache.get(tag_value, 0) < tags_min_count_download if tags_min_count_download else False
            dg_bc_none = (tags_min_count_download is None)
            if dg_bc_threshhold or dg_bc_none:
                actions.add_downloader_tags.remove(tag_value)
                # if not actions.info_only:
                #     actions.info_only = []
                actions.info_only.append(tag_value)

    return actions
