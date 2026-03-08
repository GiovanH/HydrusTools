import tqdm
import argparse
from collections import Counter
from dataclasses import dataclass
from itertools import combinations, permutations
import logging
import pprint
from typing import Any, DefaultDict
import hydrus_api
from requests.exceptions import HTTPError

from hydrustools import htlogging
from hydrustools.lookup.registry import MetadataActions, get_plugins, postprocessSuggestions

from .. import logic

logger = logging.getLogger(__name__)

group_namespace = "htgroup"

@dataclass
class BubbleItem:
    value: Any
    tags: frozenset[Any]


def reset_groups():
    for tag in logic.search_tags_re(f"{group_namespace}:*", subpattern=None):
        # logger.info(f"Deleting tag {tag.value} from {tag.count} images")
        logic.replace_tag(tag.value, new_tags=[])

def find_similar_keys(query_tagset: frozenset, groups: dict[frozenset, Any]):
    similar: list[tuple[tuple[int, ...], frozenset]] = []

    for tagset in groups.keys():
        if tagset is query_tagset:
            continue

        diff1 = tagset.difference(query_tagset) # Fewer tags
        diff2 = query_tagset.difference(tagset) # More tags
        # logger.info(f"Difference between {query_tagset} and {tagset}: {diff1} {diff2}")
        # Prefer going into a specific group you match a subset of
        # than a general group you share a trait with
        score_tup: tuple[int, ...] = (
            len(diff2), # Fewest number of fewer tags
            len(diff1), # Fewest number of additional tags
            # len(tagset), # Fewest total tags
            len(groups[tagset]) # Smallest sized group
        )
        similar.append((score_tup, tagset))

    similar.sort(key=lambda t: t[0])
    # print(query_tagset)
    # pprint.pprint(similar[:6])
    return similar

EXPAND_GROUPS = False

def bubble_group(
    all_images: list[BubbleItem],
    min_size: int,
    max_size: int,
) -> dict[frozenset[Any], list[BubbleItem]]:
    groups: dict[frozenset, list[BubbleItem]] = DefaultDict(list)

    for file in all_images:
        groups[file.tags].append(file)

    # Is there something that unifies multiple bad groups? If so, may be better to group those together

    failures = len(groups)
    # total_size = sum(len(v) for v in groups.values())

    # pbar = tqdm.tqdm(total=len(groups), unit="group")
    while failures > 0:
        # curr_size = sum(len(v) for v in groups.values())
        # if curr_size != total_size:
        #     raise ValueError(f"Total grouped entries shrank from {total_size} to {curr_size}")
        # else:
        #     print("Total item count is still", curr_size)

        failures = 0
        last_total = len(groups)
        # Sort so small groups are processed first and merged into larger ones
        sortedgroups = sorted([*groups.items()], key=lambda tf: len(tf[1]))
        for (tagset, files) in sortedgroups:
            if tagset not in groups:
                # Already popped
                logger.info(f"Skipping already-popped key {tagset}")
                continue
            if len(files) > 0 and len(files) <= min_size:
                logger.debug(f"Group {tagset} with {len(files)} members is too small")
                failures += 1

                groups.pop(tagset)

                similar = find_similar_keys(tagset, groups)
                most_similar = similar[0][-1]
                logger.debug(f"Merging into {most_similar} {len(groups[most_similar])}")

                new_list = groups[most_similar] + files
                new_key = most_similar
                if EXPAND_GROUPS and len(groups[most_similar]) == len(files):
                    assert isinstance(tagset, frozenset)
                    new_key = (tagset | most_similar)
                    groups.pop(most_similar)
                    logger.debug(f"Expanding keys {tagset} and {most_similar} to {new_key}")

                groups[new_key] = new_list

                # break
        # Sort again so large groups are broken apart first
        # for (tagset, files) in reversed(sortedgroups):
        #     if len(files) > max_size:
        #         logger.info(f"Group {tagset} with {len(files)} members is too large")
        #         finalized = False
        #         # Find most common combination of tags in group, move those items to a new group
        #         # all_tags = combinations

        #         tag_counter = Counter()
        #         for bi in files:
        #             print(bi.tags)
        #             tag_counter.update(bi.tags)

        #         pprint.pprint(tag_counter)

        #         similar = find_similar_keys(tagset, groups)
        #         pprint.pprint(similar[:6])

        #         raise NotImplementedError
        # pbar.total = len(groups)
        # pbar.update(len(groups)-failures)
        logger.info(f"Problem groups: {failures}/{last_total}")
    # pbar.close()
    return groups

def apply_groups(groups):
    for i, (tagset, items) in enumerate(groups.items()):
        tagname = f"{group_namespace}:{', '.join(tagset)}"
        if len(tagset) == 0:
            tagname = f"{group_namespace}:emptyset"
        logger.debug(f"Adding tag {tagname} for group {tagset} with {len(items)} images")
        logic.client.add_tags(
            file_ids=[bi.value['file_id'] for bi in items],
            service_keys_to_actions_to_tags={
                logic.local_tags_service_key: {
                    hydrus_api.TagAction.ADD: [tagname]
                }
            }
        )


def main():
    logic.init_client()

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("query", help="Hydrus image query")
    parser.add_argument("--ignore-namespaces", type=list, default=[
        'source', 'directory'
    ])
    parser.add_argument("--min-size", type=int, default=5)
    parser.add_argument("--max-size", type=int, default=100)
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    reset_groups()

    logger.info(f"Querying hydrus {args.query!r}...")
    resp = logic.client.search_files(
        tags=args.query.split(' AND ') # type: ignore
    )
    matching_files = resp['file_ids']
    logger.info(f"Got {len(matching_files)} ids")

    all_images: list[logic.FileMetadata] = logic.client.get_file_metadata(file_ids=matching_files, include_notes=True)['metadata']
    logger.info(f"Got {len(matching_files)} metadata sets")

    bubble_list: list[BubbleItem] = [
        BubbleItem(
            value=file,
            tags=frozenset(
                t for t in logic.local_tags(file)
                if not any(t.startswith(ns) for ns in args.ignore_namespaces)
            )
        )
        for file in all_images
    ]

    groups = bubble_group(
        bubble_list,
        min_size=args.min_size,
        max_size=args.max_size
    )

    apply_groups(groups)


if __name__ == '__main__':
    htlogging.configure_logging()
    main()