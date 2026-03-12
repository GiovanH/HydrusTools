
from collections import namedtuple
from dataclasses import dataclass
import functools
import itertools
import logging
import pprint
import re
from typing import Any, Callable, Hashable, Optional, Sequence

# TODO: Better fuzzy searching
# TODO: Use - in entry to remove tags

"""
Goals:

- Segmented search. "j e" matches "john egbert"
- Namespace support.
    - "c:e" matches "character:egbert" and "creator:engles"
    - "e" also matches "character:egbert"
- Caching. Many searches are going to be run on the same collection
- Context: Artifically increase the score for known relevant list items
- Synonyms

Don't need anymore:

- Ambiguity checking: listbox already highlights a single element
"""

logger = logging.getLogger(__name__)

# logger.setLevel(logging.DEBUG)

@functools.lru_cache()
def split_to_segments(q: str, query_split) -> tuple[str, ...]:
    # logger.info(re.split(query_split, q))
    return tuple(
        s for s in
        re.split(query_split, q)
        if s
    )


@functools.lru_cache()
def compare_segments(qseg, hseg, query_split=None, check_in=False) -> int:
    if hseg == qseg:
        return 30
    if hseg.startswith(qseg):
        return 20
    if check_in and qseg in hseg:
        return 1
    if query_split and query_split.match(qseg) and query_split.match(hseg):
        return 0
    return -1


@functools.lru_cache()
def score_segments(query_segments: tuple[str, ...], hay_segments: tuple[str, ...], query_split=None) -> int:
    score = 0

    qix = 0
    hix = 0

    while qix < len(query_segments) and hix < len(hay_segments):
        qseg = query_segments[qix]
        hseg = hay_segments[hix]

        scoredelta = compare_segments(qseg, hseg, query_split=query_split)
        logger.debug("    %s <> %s: %s", qseg, hseg, scoredelta)

        if scoredelta == -1:
            hix += 1
            continue
        else:
            logger.debug("    score %s += %s (delta)", score, scoredelta)
            score += scoredelta

            logger.debug("    score %s -= %s (hix)", score, hix)
            score -= hix

            qix += 1
            hix += 1
            continue
    if qix < len(query_segments):
        # Didn't consume query
        return 0

    len_pen = len([h for h in hay_segments if len(h) > 1])
    logger.debug("    score %s -= %s (length)", score, len_pen)
    score -= len_pen

    return score

def merge_lists(
    *lists: list[tuple[int, str]],
    edits: list = []
) -> list[str]:

    results = []
    for sublist in lists:
        for item in sublist:
            for p in edits:
                item = p(item)
            results.append(item)

    results.sort(reverse=True)

    return [val for score, val in results]


@functools.lru_cache(maxsize=2048)
def perfect_search(
    collection: tuple[str, ...],
    query: str,
    query_split: re.Pattern = re.compile(r'([\\ /_:()-])'),
    score_bonus: int = 0,
    limit: int | None = None
) -> list[tuple[int, str]]:
    # Each segment in the search must match a segment in the result, in some order
    results: list[tuple[int, str]] = []

    # if len(query) > 3:
    #     collection = tuple(merge_lists(
    #         perfect_search(
    #             collection,
    #             query[:-2],
    #             query_split=query_split,
    #             score_bonus=score_bonus,
    #             limit=limit
    #         )
    #     ))

    # Filter out
    query_segments: tuple[str, ...] = split_to_segments(query, query_split)

    visited = set()
    # TODO: Always process extras and context ignoring limit. Then count the limit on collection
    for hay in collection:
        if limit and len(results) > limit:
            break

        visited.add(hay)

        logger.debug("%s <> %s", query, hay)
        score = 0

        hay_segments: tuple[str, ...] = split_to_segments(hay, query_split)

        logger.debug(f"{query_split.match(query)!r} and {query_split.match(hay)!r}")

        if query == hay:
            score += 100
        else:
            score += score_segments(query_segments, hay_segments, query_split=query_split)

        logger.debug("  scored %s", score)
        if score < 1:
            continue

        logger.debug("  score %s += %s (bonus)", score, score_bonus)
        score += score_bonus

        logger.debug("  final %s", score)

        results.append((score, hay))

    # print(query)
    # pprint.pprint(results)
    return results


@dataclass
class MatchResults:
    all: list[str]
    resolved: Optional[str]
    unique: bool

@functools.lru_cache()
def _matchSegments(q: str, query_split) -> list[str]:
    return [
        s for s in
        re.split(query_split, q)
        if s
    ]

@functools.lru_cache()
def _segmentMatches(collection: Sequence[str], query_split=r'[\\ /_:()-]'):
    grouped_segments = [
        (item, _matchSegments(item, query_split))
        for item in collection
    ]

    def lenSegmentsKey(is_):
        _item, item_segs = is_
        return len(item_segs)

    grouped_segments.sort(key=lenSegmentsKey)
    return grouped_segments

@functools.lru_cache()
def getMatches(query, collection: Sequence[str], query_split=r'[\\ /_:(-]', fuzzy=False, max_matches=64) -> MatchResults:
    matches = []

    query_segs: list[str] = _matchSegments(query, query_split)
    offsetize = True or bool(re.match(query_split, query))

    # Construct list of (item, segs) tuples sorted by the length of segments
    grouped_item_segs: list[tuple[Any, list[str]]] = _segmentMatches(collection, query_split)

    def addSegmentMatches(match_fn: Callable[[str, str], bool]):
        """Adds matches based on match_fn(theirs, ours): segmentMatches[True, False]"""
        for item, item_segs in grouped_item_segs:
            if item in matches:
                continue
            for offset in range(1 + len(item_segs) - len(query_segs)) if offsetize else [0]:
                # zipped = [*zip(item_segs, ['']*offset + query_segs)]
                zipped = [*itertools.zip_longest(
                    item_segs,
                    ([''] * offset) + query_segs,
                    fillvalue=''
                )]
                passes_test = all(match_fn(theirs, ours) for (theirs, ours) in zipped)
                # print(item, list(zipped), offset, offsetize, passes_test)
                if passes_test:
                    # print(item, item_segs, zipped)
                    matches.append(item)
                    # break
            if len(matches) > max_matches:
                break

    addSegmentMatches(lambda theirs, ours: theirs.startswith(ours))

    if len(matches) == 0 and fuzzy:
        addSegmentMatches(lambda theirs, ours: (ours in theirs))

    best = None
    if len(matches) > 0:
        best = matches[0]

    return MatchResults(resolved=best, all=matches, unique=(len(matches) == 1))

