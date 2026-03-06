import glob
import json
import logging
import os
import pprint
import re
import subprocess
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import hydrus_api
import requests
from joblib import memory

from hydrustools.inisettings import IniSettings
from hydrustools.logic import FileMetadata

from .. import logic
from . import registry

memory = memory.Memory("cache", verbose=False)

class GrabberComSettings(IniSettings):
    grabber_dir: str = ""
    grabber_sites: list[str] = []
    grabber_aliases: dict[str, str] = {
        'Gelbooru': 'gelbooru.com'
    }

Settings = GrabberComSettings(Path("lookup/grabber.ini"))


logger = logging.getLogger(__name__)

@memory.cache
def query_booru_md5(source, md5_hash) -> None | dict:
    cwd = Path(Settings.grabber_dir)
    cmd = [
        cwd.joinpath("./grabber.com"),
        "-s", source,
        "--tags", f"md5:{md5_hash}",
        '--json', '--return-images', '--max', '1'
    ]
    stdout = None
    stderr = None
    try:
        proc: subprocess.CompletedProcess = subprocess.run(cmd, cwd=cwd, capture_output=True)
        stdout = proc.stdout
        stderr = proc.stderr
        proc.check_returncode()
    except:
        logger.error(cmd)
        logger.error(stdout)
        logger.error(stderr)
        raise
    result = json.loads(stdout)
    if len(result) == 0:
        # raise ValueError("Matched no images")
        return None
    if len(result) > 1:
        raise ValueError("Matched multiple images")
    result = result[0]
    # if result.get('id') == '0':
    #     logger.error(result)
    #     logger.error(stderr)
    #     raise ValueError(f"Grabber returned no valid ID from search {md5_hash}")
    return result


@memory.cache
def query_booru_url(source, url):
    cwd = Path(Settings.grabber_dir)
    cmd = [
        cwd.joinpath("./grabber.com"),
        "-s", source,
        "--get-details", url,
        '--json'
    ]
    stdout = None
    stderr = None
    try:
        proc: subprocess.CompletedProcess = subprocess.run(cmd, cwd=cwd, capture_output=True)
        stdout = proc.stdout
        stderr = proc.stderr
        proc.check_returncode()
    except:
        logger.error(cmd)
        logger.error(stdout)
        logger.error(stderr)
        raise
    result = json.loads(stdout)
    # if result.get('id') == '0':
    #     logger.error(result)
    #     logger.error(stderr)
    #     raise ValueError(f"Grabber returned no valid ID from search {url}")
    return result

def try_get_sites():
    localappdata = os.environ.get("LOCALAPPDATA")
    sites_dir = os.path.join(localappdata, "Bionus", "Grabber", "sites")  # type: ignore
    pattern = os.path.join(sites_dir, "*", "sites.txt")

    files = glob.glob(pattern)
    for f in files:
        with open(f, "r", encoding="utf-8") as fp:
            for line in fp.read().split('\n'):
                if line and line.strip() not in {"e621.net",}:
                    yield line.strip()


if not Settings.grabber_sites:
    Settings.grabber_sites = [*set(try_get_sites())]
    print(Settings.grabber_sites)

@registry.register
class grabberComMd5Plugin(registry.LookupPlugin):
    name = "Grabber by hash"
    priority = 5

    def __init__(self) -> None:
        super().__init__()

    def match(self, metadata: FileMetadata) -> bool:
        return True

    def suggest(self, metadata: FileMetadata, setStatus = logger.info) -> registry.MetadataActions | None:
        all_sources: list[str] = [*metadata['known_urls']]

        alternate_hashes = logic.client.get_file_relationships(
            file_ids=[metadata['file_id']]
        )['file_relationships'][metadata['hash']][str(hydrus_api.DuplicateStatus.ALTERNATES)]

        resp = logic.client.get_file_hashes(
            hashes=[metadata['hash'], *alternate_hashes],
            desired_hash_type='md5',
        )
        # pprint.pprint(resp)

        md5_hashes = [*resp['hashes'].values()]

        for md5_hash in md5_hashes:
            logger.info("searching hash %s of image %s", md5_hash, metadata['file_id'])
            for source in [
                'rule34.paheal.net',
                # "gelbooru.com",
                "hypnohub.net",
                "e621.net",
                "rule34.xxx",
                "rule34.us"
            ]:
                # if source not in Settings.grabber_sites:
                #     continue
                try:
                    match = query_booru_md5(source, md5_hash)
                    if not match:
                        # logger.info("%s has no results", source)
                        continue
                    # pprint.pprint(match)
                    page = match.get('url_page')
                    if page and page not in all_sources:
                        setStatus(f"Adding new URL {page} to image")
                        all_sources.append(page)
                except Exception:
                    logger.exception(source)
                    continue

        return registry.MetadataActions(
            file_id=metadata['file_id'],
            # add_tags=tags,
            add_urls=list(set(all_sources))
        )

@registry.register
class grabberComPlugin(registry.LookupPlugin):
    name = "Grabber by source"
    priority = 15

    def __init__(self) -> None:
        super().__init__()

    def matchurl(self, url: str) -> bool:
        return urllib.parse.urlparse(url).netloc in Settings.grabber_sites

    def match(self, metadata: FileMetadata) -> bool:
        return any(
            self.matchurl(u)
            for u in metadata['known_urls']
        )

    def suggest(self, metadata: FileMetadata, setStatus = logger.info) -> registry.MetadataActions | None:
        all_sources: list[str] = [*metadata['known_urls']]

        tags = []

        # pprint.pprint(metadata)

        for url in [eu for eu in all_sources if self.matchurl(eu)]:
            if url.startswith("https://rule34.paheal.net"):
                logger.info("%s Host %s known to not return metadata", self.__class__.__name__, url)
                continue

            logger.info("%s Looking up post %s", self.__class__.__name__, url)
            source = urllib.parse.urlparse(url).netloc
            source = Settings.grabber_aliases.get(source, source)
            lookup = query_booru_url(source, url)

            tags += [f'character:{c}' for c in lookup.get('character', [])]
            tags += [f'creator:{c}' for c in lookup.get('artist', [])]
            tags += [f'series:{c}' for c in lookup.get('copyright', [])]
            tags += [
                t for t in [
                    *lookup.get('general', []),
                    *lookup.get('meta', []),
                ]
            ]
            new_sources = lookup.get('sources', [])
            if lookup.get('url_page'):
                new_sources.append(lookup.get('url_page'))

            all_sources += new_sources

            # if len(tags) == 0:
            #     pprint.pprint(lookup)

        return registry.MetadataActions(
            file_id=metadata['file_id'],
            add_tags=tags,
            add_urls=list(set(all_sources))
        )