
from collections import namedtuple
from dataclasses import dataclass
import functools
import itertools
import logging
import pprint
import re
from typing import Any, Callable, Hashable, Optional, Sequence, TypeAlias

from frozendict import frozendict

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

Score = namedtuple("Score", ["accuracy", "distance", "tagcount"], defaults=[0, 0, 0])

def mzs(t1: Score, t2: Score) -> Score:
    return Score(*map(sum, zip(t1, t2)))

@functools.lru_cache(maxsize=80000)
def split_to_segments(q: str, query_split) -> tuple[str, ...]:
    # logger.info(re.split(query_split, q))
    return tuple(
        s for s in
        re.split(query_split, q)
        if s
    )


@functools.lru_cache(maxsize=8000000)
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


@functools.lru_cache(maxsize=8000000)
def score_segments(query_segments: tuple[str, ...], hay_segments: tuple[str, ...], query_split=None) -> Score:
    accuracy = 0
    distance = 0

    qix = 0
    hix = 0

    while qix < len(query_segments) and hix < len(hay_segments):
        qseg = query_segments[qix]
        hseg = hay_segments[hix]

        scoredelta = compare_segments(qseg, hseg, query_split=query_split)
        # logger.debug("    %s <> %s: %s", qseg, hseg, scoredelta)

        if scoredelta == -1:
            hix += 1
            continue
        else:
            # logger.debug("    score %s += %s (delta)", accuracy, scoredelta)
            accuracy += scoredelta

            # logger.debug("    score %s -= %s (hix)", accuracy, hix)
            accuracy -= hix

            qix += 1
            hix += 1
            continue
    if qix < len(query_segments):
        # Didn't consume query
        return Score()

    len_pen = len([h for h in hay_segments if len(h) > 1])
    # logger.debug("    distance %s (length)", len_pen)
    distance = len_pen

    return Score(accuracy=accuracy, distance=distance, tagcount=0)

def merge_lists(
    *lists: list[tuple[Score, str]],
    edits: list = [],
    count_tiebreak: None | frozendict[str, int] = None,
) -> list[str]:

    results = []
    for sublist in lists:
        for item in sublist:
            if count_tiebreak:
                value = item[1]
                tiebreak = count_tiebreak.get(value, 0)
                score = mzs(item[0], Score(tagcount=tiebreak))
                item = (score, value)
            for p in edits:
                item = p(item)
            results.append(item)

    results.sort(key=lambda l: l[0], reverse=True)

    logger.debug(perfect_search.cache_info())
    logger.debug(split_to_segments.cache_info())
    logger.debug(compare_segments.cache_info())
    logger.debug(score_segments.cache_info())

    return [val for score, val in results]


@functools.lru_cache(maxsize=8000)
def perfect_search(
    collection: tuple[str, ...],
    query: str,
    query_split: re.Pattern = re.compile(r'([\\ /_:()-])'),
    score_bonus: int = 0,
    limit: int | None = None
) -> list[tuple[Score, str]]:
    # Each segment in the search must match a segment in the result, in some order
    results: list[tuple[Score, str]] = []

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

        # logger.debug("%s <> %s", query, hay)
        score: Score = Score(0, 0, 0)

        hay_segments: tuple[str, ...] = split_to_segments(hay, query_split)

        # logger.debug(f"{query_split.match(query)!r} and {query_split.match(hay)!r}")

        if query == hay:
            score = mzs(score, Score(accuracy=100))
        else:
            score = mzs(score, score_segments(query_segments, hay_segments, query_split=query_split))

        # logger.debug("  scored %s", score)
        if score.accuracy < 1:
            # logger.debug("Reject")
            continue

        # logger.debug("  score %s += %s (bonus)", score, score_bonus)
        score = mzs(score, Score(accuracy=score_bonus))

        # logger.debug("  final %s", score)

        results.append((score, hay))

    # print(query)
    # pprint.pprint(results)
    return results

