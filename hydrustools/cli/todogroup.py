import argparse
import logging
from collections import defaultdict

import hydrus_api

from hydrustools.utils import htlogging
from hydrustools.utils.argparse_formatter import HTApFmtCls
from hydrustools.utils.hydrus import apply_tagset_groups

from ..utils import hydrus

logger = logging.getLogger(__name__)

group_namespace = "todogroup"

def reset_groups():
    for tag in hydrus.search_tags_re(f"{group_namespace}:*", subpattern=None):
        hydrus.replace_tag(tag.value, new_tags=[])


def main():
    parser = argparse.ArgumentParser(
        description="WIP!",
        formatter_class=HTApFmtCls
    )
    parser.add_argument("tags", nargs="+")

    args = parser.parse_args()

    hydrus.init_client()

    reset_groups()

    if len(args.tags) == 0:
        logger.info("No query, just resetting groups.")
        return

    ors: hydrus_api.OrQuery = args.tags
    query: hydrus_api.AndQuery = [ors]

    tag_set = set(args.tags)

    logger.info(f"Querying hydrus {query!r}...")
    resp = hydrus.client.search_files(
        tags=query,
        tag_service_key=hydrus.local_tags_service_key

    )
    rel_files = resp['file_ids']

    groups: defaultdict[frozenset[str], list[hydrus_api.FileMetadata]] = defaultdict(list)

    for file_meta in hydrus.client.get_file_metadata(
        file_ids=rel_files
    )['metadata']:
        file_tags = hydrus.local_tags(file_meta)
        intersection = frozenset(tag_set.intersection(file_tags))

        groups[intersection].append(file_meta)

    apply_tagset_groups(group_namespace, groups)


if __name__ == '__main__':
    htlogging.configure_logging()
    main()