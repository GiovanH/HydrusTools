from dataclasses import dataclass
import pprint
from hydrustools.utils.hydrus import FileMetadata, local_tags
from hydrustools.utils import hydrus
from . import registry

@registry.register
class DownloaderTagsPlugin(registry.LookupPlugin):
    name = "dltags"

    def match(self, metadata: FileMetadata) -> bool:
        return hydrus.downloader_tags_service_key is not None and (len(local_tags(metadata, service_key=hydrus.downloader_tags_service_key)) > 0)

    def suggest(self, metadata: FileMetadata, setStatus) -> registry.MetadataActions:
        return registry.MetadataActions(
            metadata['file_id'],
            add_tags=local_tags(metadata, service_key=hydrus.downloader_tags_service_key)
        )

