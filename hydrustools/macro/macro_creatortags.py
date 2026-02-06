import logging
import re

import tqdm
from tqdm.tk import tqdm as tqdmtk

from .. import logic
from ..component.tagadderwin import TagAction, TagAdderWindow

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def has_note(notename: str, max_n: int = 4) -> list[str]:
    return [
        *[f'system:has note with name "{notename}"'],
        *[f'system:has note with name "{notename} ({n})"' for n in range(1, max_n)]
    ]

def all_creator_names(min_count=2):
    creator_tags = logic.client.search_tags(
        search="creator:*",
        tag_service_key=logic.local_tags_service_key,
        tag_display_type="display"
    )['tags'] # type: ignore
    creator_names = [
        tag['value'].replace('creator:', '').replace(' (artist)', '')
        for tag in creator_tags
        if tag['count'] >= min_count
    ]
    return creator_names

def all_creator_patterns(creator_names) -> list[tuple[str, re.Pattern]]:
    creator_patterns: list[tuple[str, re.Pattern]] = []

    for name in creator_names:
        try:
            if name not in {'anonymous', 'unknown', 'anon', 'unknown artist'}:
                creator_patterns.append((name, re.compile(rf'(^|\b|[_+-]){re.escape(name)}(\b|[_+-])')))
        except:
            logger.error(f"Couldn't create search pattern for name {name=!r}")
            continue

    return creator_patterns

def find_creators(tk=True):
    tqdm_iterator = (tqdmtk if tk else tqdm.tqdm)

    creator_names = all_creator_names()
    creator_patterns: list[tuple[str, re.Pattern]] = all_creator_patterns(creator_names)

    notename = "filename"

    tag_query: list[str | list[str]] = [] # type: ignore

    tag_query.append(has_note(notename))
    tag_query.append("-creator:*")

    file_ids_with_note = logic.client.search_files(
        tags=tag_query # type: ignore
    )['file_ids']

    logger.info(f"Found {len(file_ids_with_note)} files matching {tag_query!r}...")

    tag_actions: list[TagAction] = []

    iterable = tqdm_iterator(
        [*logic.chunk(file_ids_with_note, 200)],
        desc=f"Searching for any of {len(creator_names)} creator tags in filenames",
        unit="chunk"
    )

    for id_chunk in iterable:
        resp = logic.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

        for metadata in resp['metadata']:
            note_body = metadata['notes'].get(notename)
            for (name, pattern) in creator_patterns:
                match = pattern.search(note_body)
                if not match:
                    continue

                new_tag = f"creator:{name}"

                logger.info(f"Adding new tag {new_tag} to file {note_body} matching {match}")

                action = TagAction(metadata['file_id'], note_body, [new_tag])
                tag_actions.append(action)

        if len(tag_actions) > 512:
            break

    if hasattr(iterable, 'close'):
        iterable.close()

    TagAdderWindow(tag_actions)


if __name__ == "__main__":
    logic.init_client()
    find_creators(tk=False)
