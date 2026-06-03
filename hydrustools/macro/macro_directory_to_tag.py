import logging
import re
import threading

import tqdm
from tqdm.tk import tqdm as tqdmtk

from pathlib import Path
from hydrustools.utils import htlogging, querylang
import hydrustools.utils.util

from ..component.tag_adder_window import TagAction, TagAdderWindow

from ..utils import hydrus

logger = logging.getLogger(__name__)

def add_page_tags(tk=True):
    """Macro: Searches filename and filepath notes for something that looks like a page number, then proposes adding the appropriate page: tag.
    """
    NOTE_NAME = 'filedir'
    TAG_NAMESPACE = 'directory'

    tag_query: querylang.Query = ['directory:funny reindeer girl']

    tag_query.append(hydrus.has_note(NOTE_NAME))

    resp = hydrus.client.search_files(
        tags=tag_query
    )
    file_ids_with_note = resp['file_ids']

    logger.info(f"Found {len(file_ids_with_note)} files matching {tag_query!r}...")

    tag_actions: list[TagAction] = []

    tqdm_iterator = (tqdmtk if tk else tqdm.tqdm)

    iterable = tqdm_iterator(
        [*hydrustools.utils.util.chunk(file_ids_with_note, 1000)],
        desc="Searching for page names in filenames",
        unit="chunk",
        leave=False
    )
    for id_chunk in iterable:

        # pw.pb['value'] = 100*i/len(chunk_list)

        resp = hydrus.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

        for metadata in resp['metadata']:
            for filedir in metadata['notes'][NOTE_NAME].split('\n'):
                try:
                    p = Path(filedir).relative_to("L:/Stash/")
                except ValueError:
                    continue
                for subdir in [p, *p.parents]:

                    dirstr = subdir.as_posix()
                    if str(dirstr) == ".":
                        continue

                    new_tag = f"{TAG_NAMESPACE}:{dirstr}"
                    if new_tag in hydrus.local_tags(metadata):
                        continue

                    # pw.setStatus(f"Found new tag {new_tag} for file {note_body} matching {match}")

                    action = TagAction(metadata['file_id'], filedir, [new_tag])
                    tag_actions.append(action)

    if isinstance(iterable, tqdmtk):
        iterable.leave = False
        iterable.close()

    # pw.destroy()

    TagAdderWindow(tag_actions)

def start():
    thread = threading.Thread(target=add_page_tags)
    thread.start()

if __name__ == "__main__":
    htlogging.configure_logging()
    hydrus.init_client()

    add_page_tags(tk=False)
