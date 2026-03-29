import logging
from dataclasses import dataclass

import hydrus_api
from hydrus_api import AndQuery, Literal

from hydrustools.settings import HTSettings, settings_section
from hydrustools.utils import htlogging

from ..utils import hydrus

logger = logging.getLogger(__name__)

@dataclass
class QueryAction():
    query: AndQuery
    reason: str | None = None
    confirm: bool | None = None
    add_tags: list[str] | None = None
    remove_tags: list[str] | None = None
    image_action: Literal['DELETE', 'FAVORITE', 'INBOX', 'ARCHIVE'] | None = None

@settings_section(section="MacroRules")
class Settings(HTSettings):
    tags_delete: list[str] = []
    tags_flatten_to_parents: list[str] = []
    # delete_query_matches: dict[str, list] = {}
    query_actions: list[QueryAction] = []

def disambiguate_chars_in_series(series: str, characters: list[str]):
    for character in characters:
        char_tag = f'character:{character}'
        hydrus.replace_tag_in_query(
            char_tag,
            [f'character:{character} ({series})'],
            [char_tag, f'series:{series}']
        )

def maybe_confirm(qa: QueryAction) -> bool:
    if qa.confirm:
        resp = input("Continue? Y/N > ")
        return resp.lower() == 'y'
    return True


def apply_query_action(qa: QueryAction):
    print(qa)

    file_ids = hydrus.client.search_files(
        tags=qa.query,
        tag_service_key=hydrus.local_tags_service_key
    )['file_ids']

    msg = f"Query {qa.query} matcheed {len(file_ids)} images"
    if len(file_ids) < 1:
        logger.debug(msg)
        return

    logger.info(msg)

    if qa.add_tags or qa.remove_tags:
        add_tags = qa.add_tags or []
        remove_tags = qa.remove_tags or []

        hydrus.add_implying_siblings(remove_tags)

        logger.info(f"Adding {add_tags} and removing {remove_tags} from {len(file_ids)} matching images")
        if not maybe_confirm(qa): return

        hydrus.client.add_tags(
            file_ids=file_ids,
            service_keys_to_actions_to_tags={
                hydrus.local_tags_service_key: {
                    hydrus_api.TagAction.ADD: add_tags,
                    hydrus_api.TagAction.DELETE: remove_tags
                }
            }
        )

    if qa.image_action == 'DELETE':
        if not qa.reason:
            raise ValueError("A reason is required to delete images")

        if qa.confirm is None:
            qa.confirm = True

        logger.info(f"Deleting {len(file_ids)} images")
        if not maybe_confirm(qa): return
        hydrus.client.delete_files(
            file_ids=file_ids,
            reason=qa.reason
        )
    if qa.image_action == 'FAVORITE':
        raise NotImplementedError()
    if qa.image_action == 'INBOX':
        raise NotImplementedError()
    if qa.image_action == 'ARCHIVE':
        raise NotImplementedError()


def run(tk=True):

    for source_tag in Settings.tags_flatten_to_parents:
        hydrus.flatten_tag_to_parents(source_tag)

    disambiguate_chars_in_series(
        'totally spies',
        ['alex', 'clover', 'sam']
    )

    query_actions = [*Settings.query_actions]

    for tag_name in Settings.tags_delete:
        query_actions.append(
            QueryAction(
                query=[tag_name],
                remove_tags=[tag_name]
            )
        )

    for qa in query_actions:
        try:
            apply_query_action(qa)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    hydrus.init_client()
    htlogging.configure_logging()
    hydrus.logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    run(tk=False)
