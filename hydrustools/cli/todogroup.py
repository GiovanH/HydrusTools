import argparse
import logging
from collections import defaultdict

import hydrus_api

from hydrustools.utils import htlogging, querylang
from hydrustools.utils.argparse_formatter import HTApFmtCls
from hydrustools.utils.hydrus import apply_tagset_groups

from ..utils import hydrus

logger = logging.getLogger(__name__)

group_namespace = "todogroup"

def reset_groups():
    for tag in hydrus.search_tags_re(f"{group_namespace}:*", subpattern=None):
        hydrus.replace_tag(tag.value, new_tags=[])


def define_parser(parser):
    parser.add_argument("-d", "--descendants", action="store_true", help="Also collect any descendants of the supplied tags")
    parser.add_argument("tags", nargs="*", help="List of tags. You can also provide an OR query and HT will try to parse it into tags.")

    parser.set_defaults(func=main)
    return parser


def main(args):
    hydrus.init_client()

    if not args.tags or len(args.tags) == 0:
        logger.info("No query, just resetting groups.")
        reset_groups()
        return

    if len(args.tags) == 1 and " OR " in args.tags[0]:
        query: hydrus_api.AndQuery = querylang.parse_ml_query(args.tags[0])
        tags = list(query[0])
    else:
        tags = args.tags

    if args.descendants:
        all_relationships = hydrus.get_relationship_info(tags)
        for si in all_relationships:
            tags.extend(si.descendants)

    tag_set = set(tags)
    ors: hydrus_api.OrQuery = [*tag_set]
    query = [ors]

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

    # print(groups)

    apply_tagset_groups(group_namespace, groups, total=True)


if __name__ == '__main__':
    htlogging.configure_logging()

    parser = argparse.ArgumentParser(
        formatter_class=HTApFmtCls
    )
    define_parser(parser)
    args = parser.parse_args()
    args.func(args)
