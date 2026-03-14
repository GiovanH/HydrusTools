from dataclasses import dataclass
from hydrustools.utils.hydrus import FileMetadata
from . import registry

@registry.register
class MyPlugin(registry.LookupPlugin):
    name = "FooPlugin"

    def match(self, metadata: FileMetadata) -> bool:
        return True

    def suggest(self, metadata: FileMetadata, setStatus) -> registry.MetadataActions:
        return registry.MetadataActions(
            metadata['file_id'],
            add_tags=['foo']
        )
