from collections import Counter
from dataclasses import dataclass
import logging
from pathlib import Path
import pprint
import re
from hydrustools.inisettings import IniSettings
from hydrustools.logic import FileMetadata
from . import registry

import time
from joblib import memory
import requests
from .. import logic

e621_url_pattern: re.Pattern[str] = re.compile(r'https?://e621.net/posts/(?P<id>\d+)/?')

memory = memory.Memory("cache")

class e621Settings(IniSettings):
    e621_user: str = ""
    e621_api_key: str = ""

Settings = e621Settings(Path("lookup/e621.ini"))

logger = logging.getLogger(__name__)

@memory.cache
def lookup_e621(e621_url):
    time.sleep(1)
    response = requests.get(
        f"{e621_url}.json?login={Settings.e621_user}&api_key={Settings.e621_api_key}",
        headers={
            'User-Agent': 'HydrusTool/1.0 (by GiovanH)',
            'Content-Type': 'application/json'
        }
    )
    try:
        response.raise_for_status()
    except:
        print(response.text)
        raise
    return response.json()['post']

@registry.register
class e621Plugin(registry.LookupPlugin):
    name = "e621"

    def __init__(self) -> None:
        super().__init__()

        resp = logic.client.search_tags(
            search="*",
            tag_service_key=logic.local_tags_service_key,
            tag_display_type="storage"
        )
        self.tag_whitelist: set[str] = {
            t['value']
            for t in resp['tags']  # type: ignore
            if ":" not in t['value']
        }
        self.tag_whitelist.intersection_update({t.replace(' ', '_') for t in self.tag_whitelist})

    def match(self, metadata: FileMetadata) -> bool:
        # pprint.pprint(metadata)
        return any(
            e621_url_pattern.match(u)
            for u in metadata['known_urls']
        )

    def suggest(self, metadata: FileMetadata, setStatus = logger.info) -> registry.MetadataActions | None:
        filtered_tags = Counter()

        for eu in [eu for eu in metadata['known_urls'] if e621_url_pattern.match(eu)]:
            # print(file_metadata)
            setStatus("Looking up e621 post %s" % eu)
            lookup = lookup_e621(eu)
            # pprint.pprint(lookup)

            tags = []
            # tags += [f'series:{c}' for c in lookup['tags']['copyright']]
            tags += [f'character:{c}' for c in lookup['tags']['character']]
            tags += [f'creator:{c}' for c in lookup['tags']['artist']]
            tags += [
                t for t in [
                    *lookup['tags']['general'],
                    *lookup['tags']['lore'],
                    *lookup['tags']['meta'],
                    *lookup['tags']['copyright']
                ]
                # if t in self.tag_whitelist
            ]
            sources = lookup['sources']

            # downloader_tags = [
            #     *lookup['tags']['general'],
            #     *lookup['tags']['lore'],
            #     *lookup['tags']['meta'],
            #     *[f'series:{c}' for c in lookup['tags']['copyright']],
            #     *[f'species:{c}' for c in lookup['tags']['species']],
            # ]
            # filtered_tags.update([t for t in downloader_tags if t not in tags])
            # downloader_tags = []
            # tags = [t.replace('_', ' ') for t in tags]

            # TODO move to window
            tags = [t.replace('_', ' ') for t in tags]

            # pprint.pprint((tags, sources))

            return registry.MetadataActions(
                file_id=metadata['file_id'],
                add_tags=tags,
                add_urls=sources
            )
