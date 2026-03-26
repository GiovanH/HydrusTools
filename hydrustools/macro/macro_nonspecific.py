import logging

import hydrus_api

from hydrustools.settings import HTSettings, settings_section
from hydrustools.utils import htlogging, querylang
from hydrustools.utils.namespace import get_tag_namespace

from ..utils import hydrus

logger = logging.getLogger(__name__)

# @settings_section(section="MacroRules")
# class Settings(HTSettings):
#     tags_delete: list[str] = []
#     tags_flatten_to_parents: list[str] = []
#     flatten_presearch_hl: list[str] = []
#     flatten_search: str = ""
#     flatten_search_hl: list[str] = []



def run(tk=True):

    all_tag_counts = hydrus.search_tags_re('*', subpattern=None, display_type='display')
    all_tags = [t.value for t in all_tag_counts if t.count > 0]
    all_relationships = hydrus.get_relationship_info(all_tags)

    for si in all_relationships:
        if si.tag != si.ideal_tag:
            continue
        if get_tag_namespace(si.tag):
            continue
        nns_descendants = [
            d for d in si.descendants
            if not get_tag_namespace(d)
        ]
        if len(nns_descendants) < 1:
            continue

        query: hydrus_api.AndQuery = [
            si.tag,
            *(
                f"-{d}"
                for d in nns_descendants
            )
        ]

        print(querylang.serialize_query_sl(query))


if __name__ == "__main__":
    hydrus.init_client()
    htlogging.configure_logging()
    hydrus.logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    run(tk=False)
