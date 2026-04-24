import io
import logging
import pprint
import time
from pathlib import Path

import requests
from joblib import memory

from hydrustools.settings import HTSettings, settings_section
from hydrustools.utils.hydrus import FileMetadata

from ..utils import hydrus
from ..utils.util import timer
from . import registry

memory = memory.Memory("cache", verbose=False)

@settings_section(section="SauceNao", file="Lookup")
class Settings(HTSettings):
    api_key: str = ""
    enabled_sites: list[str] = [
        'pixiv',
        'danbooru',
        'yandere',
        'gelbooru',
        'konachan',
        # 'e621'
    ]  # noqa: RUF012
    numres: int = 1
    minsim: int = 90

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


@memory.cache
def sauce_from_hydrus(metadata: FileMetadata, minsim, numres, thumbnail=True):
    if thumbnail:
        with timer("thumbnail"):
            resp = hydrus.client.get_thumbnail(file_id=metadata['file_id'])
            resp.raise_for_status()

        imageData = io.BytesIO(resp.content)
    else:
        with timer("render"):
            resp = hydrus.client.get_render(file_id=metadata['file_id'])
            resp.raise_for_status()

        imageData = io.BytesIO(resp.content)


    result = None
    retries = 0
    while (not result) or (result.get('header', {}).get('status') != 0):
        logger.debug(pprint.pformat(result))
        if result:
            logger.debug(f"{result.get('header', {}).get('status')=!r}")
        try:
            resp = requests.post(
                "http://saucenao.com/search.php",
                params={
                    "output_type": 2,
                    "numres": numres,
                    "minimum_similarity": f"{minsim}",
                    # "dbmask": str(bitmask),
                    "db": 999,
                    "api_key": Settings.api_key
                },
                timeout=10,
                files={'file': ("image.png", imageData.getvalue())}
            )
            logger.debug(resp)
            result = resp.json()
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(e)
            logger.error(result)

            if result and "Daily Search Limit Exceeded." in result.get('header', {}).get('message', ''):
                raise ConnectionRefusedError(result)

            if result and "Search Rate Too High." in result.get('header', {}).get('message', ''):
                logger.info("Waiting 35 secs...")
                time.sleep(35)
                retries += 1
                if retries < 2:
                    continue

            raise ConnectionRefusedError(result)
    return result

@registry.register
class sauceNaoPlugin(registry.LookupPlugin):
    name = "Saucenao"
    priority = registry.PRIOR_BY_HASH

    def __init__(self) -> None:
        super().__init__()

        self.refused = False
        # self.client = pysaucenao.SauceNao(
        #     api_key=Settings.api_key,
        # )

    def match(self, metadata: FileMetadata) -> bool:
        return bool(Settings.api_key) and (not self.refused)

    def suggest(self, metadata: FileMetadata, setStatus = logger.info) -> registry.MetadataActions | None:

        act = registry.MetadataActions(
            source=self,
            file_id=metadata['file_id'],
            add_tags=[],
            add_urls=[]
        )

        assert isinstance(act.add_tags, list)

        try:
            result = sauce_from_hydrus(
                metadata,
                minsim=Settings.minsim,
                numres=Settings.numres
            )
        except ConnectionRefusedError:
            self.refused = True
            raise

        # TODO: if short_remaining == 0, self.refused = true but continue

        logger.debug(pprint.pformat(result))

        for entry in result['results']:
            if float(entry['header']['similarity']) > Settings.minsim:
                logger.debug("Good match: %s", entry)

                if entry['data'].get('ext_urls'):
                    act.add_urls += entry['data']['ext_urls']

                if entry['data'].get('title'):
                    act.add_notes.append({"title": entry ['data']['title']})
                if entry['data'].get('member_name'):
                    act.add_tags.append(f"creator:{entry['data']['member_name']}")
                if entry['data'].get('material'):
                    entry_tags: list[str] = entry['data'].get('material').split(", ")
                    act.add_tags.extend(entry_tags)
                # raise NotImplementedError
            else:
                logger.warning("Discarding insufficiently similar match %s", entry)

        return act
