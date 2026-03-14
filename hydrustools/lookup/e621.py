import logging
import re
from pathlib import Path

import requests
from joblib import memory

from hydrustools.utils.inisettings import IniSettings
from hydrustools.utils.hydrus import FileMetadata

from . import registry

e621_url_pattern: re.Pattern[str] = re.compile(r'https?://e621.net/posts?/(show/)?(?P<id>\d+)/?')

memory = memory.Memory("cache", verbose=False)

class e621Settings(IniSettings):
    e621_user: str = ""
    e621_api_key: str = ""

Settings = e621Settings(Path("lookup/e621.ini"))

logger = logging.getLogger(__name__)

@memory.cache
def lookup_e621(e621_url):
    # time.sleep(1)
    match = e621_url_pattern.match(e621_url)
    assert isinstance(match, re.Match)
    response = requests.get(
        f"https://e621.net/posts/{match.group('id')}.json?login={Settings.e621_user}&api_key={Settings.e621_api_key}",
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

    def match(self, metadata: FileMetadata) -> bool:
        # print({u: e621_url_pattern.match(u) for u in metadata['known_urls']})
        return any(
            e621_url_pattern.match(u)
            for u in metadata['known_urls']
        )

    def suggest(self, metadata: FileMetadata, setStatus = logger.info) -> registry.MetadataActions | None:
        for eu in [eu for eu in metadata['known_urls'] if e621_url_pattern.match(eu)]:
            setStatus(f"Looking up e621 post {eu}")
            lookup = lookup_e621(eu)

            tags = []
            tags += [f'character:{c}' for c in lookup['tags']['character']]
            tags += [f'creator:{c}' for c in lookup['tags']['artist']]
            tags += [f'series:{c}' for c in lookup['tags']['copyright']]
            tags += [
                t for t in [
                    *lookup['tags']['general'],
                    *lookup['tags']['lore'],
                    *lookup['tags']['meta']
                ]
            ]
            sources = lookup['sources']

            return registry.MetadataActions(
                source=self,
                file_id=metadata['file_id'],
                add_tags=tags,
                add_urls=sources
            )
