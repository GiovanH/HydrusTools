import logging
import threading
from collections import defaultdict

from hydrus_api.types import FileId, FileMetadata

import hydrustools.utils.namespace
import hydrustools.utils.util
from hydrustools.utils import htlogging

from ..component.sibling_adder_window import SiblingAction, SiblingAdderWindow
from ..utils import hydrus
from ..utils.querylang import AndQuery

import tqdm
from tqdm.tk import tqdm as tqdmtk

logger = logging.getLogger(__name__)

cache = {}

def run(tk=True):
    tag_query: AndQuery = [
        '-meta:collab',
        'system:number of creator tags > 1'
    ]

    resp = hydrus.client.search_files(
        tags=tag_query,
        tag_service_key=hydrus.local_tags_service_key
    )
    matching_ids: list[FileId] = resp['file_ids']

    matching_files: dict[int, FileMetadata] = {}
    ids_by_artists: defaultdict[frozenset, list[FileId]] = defaultdict(list)

    tqdm_iterator = (tqdmtk if tk else tqdm.tqdm)

    iterable = tqdm_iterator(
        [*hydrustools.utils.util.chunk(matching_ids, 1000)],
        desc="Gathering tags from images",
        unit="k",
        leave=False
    )

    for id_chunk in iterable:
        resp = hydrus.client.get_file_metadata(file_ids=id_chunk, include_notes=False)
        for metadata in resp['metadata']:
            matching_files[metadata['file_id']] = metadata
            key = frozenset(
                t for t in hydrus.local_tags(metadata)
                if (ns := hydrustools.utils.namespace.get_tag_namespace(t))
                and ns.name == "creator"
            )
            ids_by_artists[key].append(metadata['file_id'])

    sibling_actions: list[SiblingAction] = []

    for k, v in ids_by_artists.items():
        artists = sorted(k)

        # for main_tag in artists:
        main_tag = artists[0]
        sibling_actions.append(SiblingAction(
            main_tag,
            artists,
            f"Count: {len(v)}"
        ))

    SiblingAdderWindow(sibling_actions)


def start():
    thread = threading.Thread(target=run)
    thread.start()


if __name__ == "__main__":
    hydrus.init_client()
    htlogging.configure_logging()
    run(tk=False)
