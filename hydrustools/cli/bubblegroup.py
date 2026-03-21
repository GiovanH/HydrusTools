import argparse
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
import pprint
import statistics
from typing import Any, Literal, Protocol, TypeAlias

import hydrus_api

from hydrustools.utils import htlogging, querylang
from hydrustools.utils.argparse_formatter import HTApFmtCls
import hydrustools.utils.namespace
import hydrustools.utils.util
# from hydrustools.utils.htlogging import IterationLogHandler

from ..utils import hydrus

# When adding new tags to a group, expand the key to include all contained tags:

logger = logging.getLogger(__name__)

# iterhandler = IterationLogHandler()
# # handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
# iterhandler.setLevel(level=logging.DEBUG)
# logger.addHandler(iterhandler)

group_namespace = "htgroup"

Score: TypeAlias = tuple[int, ...]

@dataclass
class BubbleItem:
    value: Any
    tags: frozenset[Any]

@dataclass
class BubbleSettings:
    min_size: int
    max_size: int
    expand_groups: bool = False
    describe_moves: bool = False

    def logmove(self, *args):
        fn = (logger.info if self.describe_moves else logger.debug)
        fn(*args)

class GroupModHandler(Protocol):
    def __call__(
        self,
        settings: BubbleSettings,
        groups: defaultdict[frozenset, list[BubbleItem]],
        group_key: frozenset,
        group_files: list[BubbleItem]
    ) -> bool: ...

    def __name__(self) -> str: ...

def is_exact_group(group: list[BubbleItem]):
    tags = [bi.tags for bi in group]
    return tags.count(tags[0]) == len(tags)

def reset_groups():
    for tag in hydrus.search_tags_re(f"{group_namespace}:*", subpattern=None):
        # logger.info(f"Deleting tag {tag.value} from {tag.count} images")
        hydrus.replace_tag(tag.value, new_tags=[])

def find_similar_keys(
    query_tagset: frozenset,
    groups: dict[frozenset, Any]
) -> list[tuple[Score, frozenset[Any]]]:
    """Given a query (set of tags) and a set of groups (keyed by sets of tags), score the keys of the groups according to how similar they are to the query. """
    similar: list[tuple[Score, frozenset]] = []

    for tagset, file_list in groups.items():
        # logger.debug("Checking tagset key %s of %s", tagset, len(groups))
        if tagset is query_tagset:
            # logger.debug("Rejecting exact match %s", tagset)
            continue

        diff1 = tagset.difference(query_tagset) # Fewer tags
        diff2 = query_tagset.difference(tagset) # More tags
        # logger.info(f"Difference between {query_tagset} and {tagset}: {diff1} {diff2}")
        # Prefer going into a specific group you match a subset of
        # than a general group you share a trait with
        score_tup: Score = (
            len(diff2), # Fewest number of fewer tags
            len(diff1), # Fewest number of additional tags
            # Avoid breaking exact groups
            0 if is_exact_group(file_list) else 10,
            # len(tagset), # Fewest total tags
            len(file_list) # Smallest sized group
        )
        similar.append((score_tup, tagset))

    similar.sort(key=lambda t: t[0])
    # print(query_tagset)
    # pprint.pprint(similar[:6])
    return similar

def merge_small_group_into_similar(
    settings: BubbleSettings,
    groups: defaultdict[frozenset, list[BubbleItem]],
    group_key: frozenset,
    group_files: list[BubbleItem]
) -> bool:
    popped_files = groups.pop(group_key)
    try:
        assert popped_files == group_files
    except:
        print(popped_files)
        print(group_files)
        raise

    similar = find_similar_keys(group_key, groups)
    try:
        most_similar = similar[0][-1]
    except IndexError:
        logger.error("No similar groups for %s in %s", group_key, groups)
        return False
    logger.debug(f"Merging into {most_similar} {len(groups[most_similar])}")

    new_list = groups[most_similar] + group_files
    new_key = most_similar

    if settings.expand_groups and len(groups[most_similar]) == len(group_files):
        assert isinstance(group_key, frozenset)
        new_key = (group_key | most_similar)
        groups.pop(most_similar)
        logger.debug(f"Expanding keys {group_key} and {most_similar} to {new_key}")

    groups[new_key] = new_list
    return True

def _maybe_extract_tagset(
    sub_tagset: frozenset[str],
    key_count: int,
    settings: BubbleSettings,
    groups: defaultdict[frozenset, list[BubbleItem]],
    group_key: frozenset,
    group_files: list[BubbleItem],
    group_is_exact: bool
) -> Literal['CONTINUE', 'BREAK', 'TRUE']:
    # Skip this, because it may be exact and unbreakable
    # if count > max_size:
    #     logger.debug("Tagset %s with length %s is too large to extract", sub_tagset, count)
    #     return 'CONTINUE'

    # if count != len(group_files):
    #     logger.error("Got count %s, but real length is %s", count, len(group_files))
    group_count = len(group_files)

    if group_count < settings.min_size:
        logger.debug("Tagset %s with length %s is too small to extract", sub_tagset, group_count)
        return 'BREAK' # list is sorted, no good groups past this point

    if sub_tagset in groups:
        logger.debug("Tagset %s is already a group with size %s", sub_tagset, len(groups[sub_tagset]))
        new_size = len(groups[sub_tagset]) + group_count
        if new_size > settings.max_size:
            logger.debug("...which would be %s + %s = %s, too big.", group_count, len(groups[sub_tagset]), new_size)
            return 'CONTINUE'
        logger.debug("...which can still work! %s <= %s", new_size, settings.max_size)

    settings.logmove("Extracting tagset %s from %s", sub_tagset, group_key)

    new_key = sub_tagset
    new_list = groups[new_key]

    for bi in group_files:
        group_files.remove(bi)
        new_list.append(bi)

    groups[new_key] = new_list
    groups[group_key] = group_files

    return 'TRUE'

def shrink_large_group_by_extracting_set(
    settings: BubbleSettings,
    groups: defaultdict[frozenset, list[BubbleItem]],
    group_key: frozenset,
    group_files: list[BubbleItem]
) -> bool:
    tagset_counter: Counter[frozenset] = Counter()
    for bi in group_files:
        tagset_counter[bi.tags] += 1

    logger.debug("Tagset Distribution")
    logger.debug(pprint.pformat(tagset_counter))

    # Remove smallest set big enough to be a group
    for sub_tagset, count in tagset_counter.most_common():
        maybe = _maybe_extract_tagset(
            sub_tagset=sub_tagset,
            key_count=count,
            settings=settings,
            groups=groups,
            group_key=group_key,
            group_files=group_files,
            group_is_exact=True
        )
        if maybe == 'TRUE': return True
        elif maybe == 'CONTINUE': continue
        elif maybe == 'BREAK': break
        else: raise NotImplementedError(maybe)

    return False

def shrink_large_group_by_tag_distribution(
    settings: BubbleSettings,
    groups: defaultdict[frozenset, list[BubbleItem]],
    group_key: frozenset,
    group_files: list[BubbleItem]
) -> bool:
    tag_counter: Counter[str] = Counter()
    for bi in group_files:
        tag_counter.update(bi.tags)

    logger.debug("Tag Distribution")
    logger.debug(pprint.pformat(tag_counter))

    # Remove smallest tag big enough to be a group
    for sub_tag, count in tag_counter.most_common():
        sub_tagset = frozenset([sub_tag])
        maybe: Literal['CONTINUE', 'BREAK', 'TRUE'] = _maybe_extract_tagset(
            sub_tagset=sub_tagset,
            key_count=count,
            settings=settings,
            groups=groups,
            group_key=group_key,
            group_files=group_files,
            group_is_exact=False
        )
        if maybe == 'TRUE': return True
        elif maybe == 'CONTINUE': continue
        elif maybe == 'BREAK': break
        else: raise NotImplementedError(maybe)

    return False

def shrink_large_group_by_tag_similarity(
    settings: BubbleSettings,
    groups: defaultdict[frozenset, list[BubbleItem]],
    group_key: frozenset,
    group_files: list[BubbleItem]
) -> bool:
    logger.debug("Similarity %s", group_key)
    similar: list[tuple[tuple[int, ...], frozenset[Any]]] = find_similar_keys(group_key, groups)
    logger.debug(pprint.pformat(similar[:6]))

    for score, sub_tagset in similar:
        count = score[-1]
        maybe = _maybe_extract_tagset(
            sub_tagset=sub_tagset,
            key_count=count,
            settings=settings,
            groups=groups,
            group_key=group_key,
            group_files=group_files,
            group_is_exact=False
        )
        if maybe == 'TRUE': return True
        elif maybe == 'CONTINUE': continue
        elif maybe == 'BREAK': break
        else: raise NotImplementedError(maybe)

    return False

def shrink_large_group_by_force(
    settings: BubbleSettings,
    groups: defaultdict[frozenset, list[BubbleItem]],
    group_key: frozenset,
    group_files: list[BubbleItem]
) -> bool:
    group_size = settings.max_size - settings.min_size
    logger.error("Force-dividing large group %s (%s) into %sx chunks", group_key, len(group_files), group_size)
    for i, bichunk in enumerate(hydrustools.utils.util.chunk(group_files, group_size)):
        for bi in bichunk:
            bi.tags = frozenset([*bi.tags, f"force{i}"])

    groups[group_key] = group_files
    return True

def bubble_group(
    all_images: list[BubbleItem],
    settings: BubbleSettings,
) -> dict[frozenset[Any], list[BubbleItem]]:
    groups: dict[frozenset, list[BubbleItem]] = defaultdict(list)

    for file in all_images:
        groups[file.tags].append(file)

    # Is there something that unifies multiple bad groups? If so, may be better to group those together

    failures_big = len(groups)
    failures_small = len(groups)
    failures_big_last = -1
    failures_small_last = -1
    total_size = sum(len(v) for v in groups.values())

    def repr_groups():
        return pprint.pformat({k: f"{len(v)}{' (exact)' if is_exact_group(v) else ''}" for k, v in groups.items()})

    last_size_repr: str = ""

    def check_size():
        nonlocal total_size
        nonlocal last_size_repr

        curr_size = sum(len(v) for v in groups.values())
        if curr_size != total_size:
            logger.error("Prev: %s", last_size_repr)

            logger.error("Now: %s", repr_groups())
            raise ValueError(f"Total grouped entries shrank from {total_size} to {curr_size}")
        else:
            # print("Total item count is still", curr_size)
            last_size_repr = repr_groups()

    # pbar = tqdm.tqdm(total=len(groups), unit="group")
    while (failures_big + failures_small) > 0:
        # check_size()

        failures_big = 0
        failures_small = 0
        last_total = len(groups)
        # Sort so small groups are processed first and merged into larger ones
        sortedgroups = sorted([*groups.items()], key=lambda tf: len(tf[1]))
        for (tagset, __) in sortedgroups:
            if tagset not in groups:
                # Already popped
                logger.debug(f"Skipping already-popped key {tagset}")
                continue
            # Re-fetch files
            files = groups[tagset]

            if len(files) > 0 and len(files) < settings.min_size:
                logger.debug(f"Group {tagset} with {len(files)} members is too small")
                failures_small += 1

                merged = False
                mergers: list[GroupModHandler] = [
                    merge_small_group_into_similar
                ]
                for merger in mergers:
                    merged = merger(
                        settings=settings,
                        groups=groups,
                        group_key=tagset,
                        group_files=files
                    )
                    if merged:
                        # check_size()
                        break
                    else:
                        logger.warning(f"Couldn't merge group {tagset} {len(files)} using {merger.__name__}")

                if not merged:
                    raise NotImplementedError(f"Couldn't merge group {tagset} {len(files)} into any of {repr_groups()}")

        # Sort again so large groups are broken apart first
        for (tagset, files) in reversed(sortedgroups):
            if len(files) > settings.max_size:
                settings.logmove(f"Group {tagset} with {len(files)} members is too large")

                if is_exact_group(files):
                    settings.logmove("...but the group is exact, so nothing we can do here.")
                    continue

                failures_big += 1

                shrunk = False
                shrinkers: list[GroupModHandler] = [
                    shrink_large_group_by_extracting_set,
                    shrink_large_group_by_tag_distribution,
                    shrink_large_group_by_tag_similarity,
                    shrink_large_group_by_force,
                ]
                for shrinker in shrinkers:
                    shrunk = shrinker(
                        settings=settings,
                        groups=groups,
                        group_key=tagset,
                        group_files=files
                    )
                    if shrunk:
                        # check_size()
                        break
                    else:
                        logger.warning(f"Couldn't shrink group {tagset} {len(files)} using {shrinker.__name__}")

                if not shrunk:
                    raise NotImplementedError(f"Couldn't shrink group {tagset} {len(files)} into any of {repr_groups()}")

        # pbar.total = len(groups)
        # pbar.update(len(groups)-failures)
        logger.debug("%s", repr_groups())
        logger.info(f"Last problem groups: {failures_small} small, {failures_big} large out of {last_total}")

        if (failures_small == failures_small_last) and (failures_big == failures_big_last) and (len(groups) == last_total):
            raise AssertionError("Loop detected!")

        failures_small_last = failures_small
        failures_big_last = failures_big
    # pbar.close()
    return groups

def apply_groups(groups):
    all_tagsets: list[frozenset] = [*groups.keys()]
    for i, (tagset, items) in enumerate(groups.items()):
        # Clean up names
        name_tagset = set()
        for n in tagset:
            if not all(n in set for set in all_tagsets) and not n.startswith("-"):
                name_tagset.add(hydrustools.utils.namespace.get_tag_unnamespaced_value(n))

        tagname = f"{group_namespace}:{', '.join(name_tagset)}"
        if len(tagset) == 0:
            tagname = f"{group_namespace}:emptyset"

        logger.info(f"Adding tag {tagname} for group {tagset} with {len(items)} images")
        hydrus.client.add_tags(
            file_ids=[bi.value['file_id'] for bi in items],
            service_keys_to_actions_to_tags={
                hydrus.local_tags_service_key: {
                    hydrus_api.TagAction.ADD: [tagname]
                }
            }
        )
    logger.info("Divided images into %s groups.", len(groups))


def main():
    hydrus.init_client()

    parser = argparse.ArgumentParser(
        description="WIP!",
        formatter_class=HTApFmtCls
    )
    parser.add_argument("query", help="Hydrus image query")
    parser.add_argument("--ignore-namespaces", type=list, default=[
        'source', 'directory'
    ])
    parser.add_argument("--min-size", type=int, default=5, help=':')
    parser.add_argument("--max-size", type=int, default=100, help=':')
    parser.add_argument("--sort-on-attributes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include extra sorting attributes for audio/video, tag count, etc"
    )
    parser.add_argument("--expand-groups",
        action=argparse.BooleanOptionalAction,
        default=BubbleSettings.expand_groups,
        help="Internal algorithm tweak"
    )
    parser.add_argument("--describe-moves", action="store_true")
    parser.add_argument("--alias-tags", action="store_true")
    parser.add_argument("--add-not-tags", action="store_true")
    parser.add_argument("--force", action="store_true",
        help="Force groups to work even if there is no logical division by dividing along arbitrary lines.")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    assert args.min_size > 0
    assert args.max_size > args.min_size

    reset_groups()

    logger.info(f"Querying hydrus {args.query!r}...")
    resp = hydrus.client.search_files(
        tags=querylang.parse_sl_query(querylang.SLQuery(args.query)),
        tag_service_key=hydrus.local_tags_service_key

    )
    matching_files = resp['file_ids']
    logger.info(f"Got {len(matching_files)} ids, getting metadata...")

    all_images: list[hydrus.FileMetadata] = hydrus.client.get_file_metadata(file_ids=matching_files, include_notes=True)['metadata']
    logger.info(f"Got {len(matching_files)} metadata sets")

    bubble_list: list[BubbleItem] = []

    for file in all_images:
        local_tags = [
            t for t in
            hydrus.local_tags(file)
            if not any(t.startswith(ns) for ns in args.ignore_namespaces)
        ]
        tags = [*local_tags]
        if args.sort_on_attributes:
            tags.extend(filter(bool, [
                "audio" if file.get('has_audio') else None,
                "animation" if (file.get('num_frames') or 0)>1 else None,
                "few tags" if len(local_tags) < 3 else None,
            ])) # type: ignore
        bubble_list.append(BubbleItem(
            value=file,
            tags=frozenset(tags)
        ))

    if args.force:
        group_size = args.max_size - args.min_size
        for i, bichunk in enumerate(hydrustools.utils.util.chunk(bubble_list, group_size)):
            for bi in bichunk:
                bi.tags = frozenset([*bi.tags, f"force{i}"])


    all_tags: Counter[str] = Counter()
    for bi in bubble_list:
        all_tags.update(bi.tags)

    if args.add_not_tags:
        average = int(statistics.mean(all_tags.values()))
        logger.info("Adding not tags with threshhold %s", average)
        for bi in bubble_list:
            tags = set(bi.tags)
            for tag, count in all_tags.items():
                if count > average:
                    if tag not in tags:
                        tags.add(f"-{tag}")
            bi.tags = frozenset(tags)


    if args.alias_tags:
        logger.info("Aliasing tags")
        tag_list = [*all_tags.values()]
        for bi in bubble_list:
            bi.tags = frozenset([
                hex(tag_list.index(tag))[1:].upper()
                for tag in bi.tags
            ])




    logger.info("Grouping %s items...", len(bubble_list))
    try:
        groups = bubble_group(
            bubble_list,
            settings=BubbleSettings(
                max_size=args.max_size,
                min_size=args.min_size,
                expand_groups=args.expand_groups,
                describe_moves=args.describe_moves
            )
        )
    except:
        # iterhandler.dump()
        raise

    apply_groups(groups)


if __name__ == '__main__':
    htlogging.configure_logging()
    main()