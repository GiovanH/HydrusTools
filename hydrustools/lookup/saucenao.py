import asyncio
import io
import logging
import pprint
import time
import typing
from io import BytesIO
from pathlib import Path

import hydrus_api

# from pysaucenao.results import SauceNaoResults
import requests
from joblib import memory

# import pysaucenao
from hydrustools.inisettings import IniSettings
from hydrustools.logic import FileMetadata

from .. import logic
from . import registry

memory = memory.Memory("cache", verbose=False)

class SauceNaoSettings(IniSettings):
    api_key: str = ""
    enabled_sites: list[str] = ['pixiv', 'danbooru', 'yandere', 'gelbooru', 'konachan', 'e621']  # noqa: RUF012
    numres: int = 1
    minsim: int = 90

Settings = SauceNaoSettings(Path("lookup/saucenao.ini"))

logger = logging.getLogger(__name__)

sauce_index_list = [
    'hmags',
    'hanime',
    'hcg',
    'ddbobjects',
    'ddbsamples',
    'pixiv',
    'pixivhistorical',
    'anime',
    'seigaillust',
    'danbooru',
    'drawr',
    'nijie',
    'yandere',
    'animeop',
    'imdb',
    'shutterstock',
    'fakku',
    'reserved',
    'nhentai',
    '2dmarket',
    'medibang',
    'anime',
    'hanime',
    'movies',
    'shows',
    'gelbooru',
    'konachan',
    'sankaku',
    'animepictures',
    'e621',
    'idolcomplex',
    'bcyillust',
    'bcycosplay',
    'portalgraphics',
    'da',
    'pawoo',
    'madokami',
    'mangadex',
    'ehentai',
    'artstation',
    'furaffinity',
    'twitter',
    'furrynetwork'
]

def get_bitmask(enabled_sites: list[str]):
    db_bitmask_bin = ''
    for i in reversed(sauce_index_list):
        if i == 'reserved':
            continue
        if i in enabled_sites:
            db_bitmask_bin = db_bitmask_bin+'1'
        else:
            db_bitmask_bin = db_bitmask_bin+'0'

    db_bitmask = int(db_bitmask_bin, 2)
    return db_bitmask


@memory.cache()
def sauce_from_hydrus(metadata: FileMetadata, bitmask, minsim, numres):
    resp = logic.client.get_thumbnail(file_id=metadata['file_id'])
    resp.raise_for_status()

    imageData = io.BytesIO(resp.content)

    result = None
    while not result:
        try:
            resp = requests.post(
                "http://saucenao.com/search.php",
                params={
                    "output_type": 2,
                    "numres": numres,
                    "minsim": f"{minsim}!",
                    "dbmask": str(bitmask),
                    "api_key": Settings.api_key
                },
                files={'file': ("image.png", imageData.getvalue())}
            )
            resp.raise_for_status()
            result = resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(e)
            logger.info("Waiting...")
            time.sleep(30)
    return result

@registry.register
class sauceNaoPlugin(registry.LookupPlugin):
    name = "Saucenao"
    priority = registry.PRIOR_BY_HASH

    def __init__(self) -> None:
        super().__init__()

        # self.client = pysaucenao.SauceNao(
        #     api_key=Settings.api_key,
        # )

    def match(self, metadata: FileMetadata) -> bool:
        return bool(Settings.api_key)

    def suggest(self, metadata: FileMetadata, setStatus = logger.info) -> registry.MetadataActions | None:

        act = registry.MetadataActions(
            source=self,
            file_id=metadata['file_id'],
            add_tags=[],
            add_urls=[]
        )

        result = sauce_from_hydrus(
            metadata,
            bitmask=get_bitmask(Settings.enabled_sites),
            minsim=Settings.minsim,
            numres=Settings.numres
        )

        # pprint.pprint(result)

        for entry in result['results']:
            if float(entry['header']['similarity']) > Settings.minsim:
                pprint.pprint(entry)
                act.add_urls += entry['data']['ext_urls']
                if entry['data'].get('member_name'):
                    act.add_tags.append(f"creator:{entry['data']['member_name']}")
                # raise NotImplementedError
            else:
                logger.debug("Discarding insufficiently similar match %s", entry['header'])

        return act
