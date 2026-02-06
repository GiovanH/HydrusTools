import logging
import re

from tqdm.tk import tqdm as tqdmtk

from ..component.tagadderwin import TagAction, TagAdderWindow

from .. import logic

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def has_note(max_n: int = 4) -> list[str]:
    return [
        *[f'system:has note with name "filename"'],
        *[f'system:has note with name "filename ({n})"' for n in range(1, max_n)],
        *[f'system:has note with name "filepath"'],
        *[f'system:has note with name "filepath ({n})"' for n in range(1, max_n)]
    ]


def getFilenameInfo(metadata: dict) -> dict[str, str] | None:
    name_matcher = re.compile(
        r'(\b|[_-])page[^0-9]?(?P<N>\d+)([^\d]|$)'
    )

    for suffix in ['', ' (1)', ' (2)', ' (3)', ' (4)']:
        body = metadata['notes'].get(f'filename{suffix}', '')
        match = name_matcher.search(body)
        if match:
            return {
                "body": body,
                **match.groupdict()
            }

        body = metadata['notes'].get(f'filepath{suffix}', '')
        match = name_matcher.search(body)
        if match:
            return {
                "body": body,
                **match.groupdict()
            }


def add_page_tags(tk=True):
    tag_query: list[str | list[str]] = [] # type: ignore

    tag_query.append(has_note())
    tag_query.append("-page:*")

    resp = logic.client.search_files(
        tags=tag_query # type: ignore
    )
    file_ids_with_note = resp['file_ids']

    logger.info(f"Found {len(file_ids_with_note)} files matching {tag_query!r}...")

    tag_actions: list[TagAction] = []

    # iterator: tqdm.tqdm = (tqdmtk if tk else tqdm.tqdm)
    iterator = tqdmtk(
        [*logic.chunk(file_ids_with_note, 1000)],
        desc="Searching for page names in filenames",
        unit="chunk"
    )
    for i, id_chunk in enumerate(iterator):

        # pw.pb['value'] = 100*i/len(chunk_list)

        resp = logic.client.get_file_metadata(file_ids=id_chunk, include_notes=True)

        for metadata in resp['metadata']:
            groupdict = getFilenameInfo(metadata)
            if groupdict is not None:
                new_tag = f"page:{groupdict.get('N')}"

                # pw.setStatus(f"Found new tag {new_tag} for file {note_body} matching {match}")

                action = TagAction(metadata['file_id'], groupdict['body'], [new_tag])
                tag_actions.append(action)

    # pw.destroy()

    TagAdderWindow(tag_actions)



if __name__ == "__main__":
    logic.init_client()
    add_page_tags(tk=False)
