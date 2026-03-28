import logging

import hydrus_api

from hydrustools.settings import HTSettings, settings_section
from hydrustools.utils import htlogging, querylang

from ..utils import hydrus

logger = logging.getLogger(__name__)

@settings_section(section="MacroRules")
class Settings(HTSettings):
    tags_delete: list[str] = []
    tags_flatten_to_parents: list[str] = []
    flatten_presearch_hl: list[str] = []
    flatten_search: str = ""
    flatten_search_hl: list[str] = []
    delete_query_matches: dict[str, list] = {}


def disambiguate_chars_in_series(series: str, characters: list[str]):
    for character in characters:
        char_tag = f'character:{character}'
        hydrus.replace_tag_in_query(
            char_tag,
            [f'character:{character} ({series})'],
            [char_tag, f'series:{series}']
        )


def run(tk=True):
    for tag_name in Settings.tags_delete:
        logger.info(f"Deleting tag {tag_name}")
        try:
            hydrus.replace_tag(tag_name, [])
        except hydrus_api.MissingParameter:
            logger.info("Nothing to do!")

    hydrus.remove_tags_from_matches(
        ['meta:bad tag'],
        ['meta:bad tag']
    )

    hydrus.remove_tags_from_matches(
        ['creator:*', 'todo:artist'],
        ['todo:artist']
    )
    hydrus.remove_tags_from_matches(
        ['series:*', 'todo:series'],
        ['todo:series']
    )

    for source_tag in Settings.tags_flatten_to_parents:
        hydrus.flatten_tag_to_parents(source_tag)

    disambiguate_chars_in_series(
        'totally spies',
        ['alex', 'clover', 'sam']
    )

    for reason, query in Settings.delete_query_matches.items():
        logger.info(f"Deleting images matching query {query} for reason {reason}")
        hydrus.delete_all_query_matches(
            reason=reason, query=query
        )


if __name__ == "__main__":
    hydrus.init_client()
    htlogging.configure_logging()
    hydrus.logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    run(tk=False)
