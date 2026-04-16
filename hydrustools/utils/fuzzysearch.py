import functools
import logging
import pprint
import re
from collections import namedtuple
from collections.abc import Mapping, Sequence

logger = logging.getLogger(__name__)

Score = namedtuple(
    "Score",
    ["accuracy", "distance", "length", "tagcount"],
    defaults=[0, 0, 0, 0]
)

_SCORE_ZERO = Score(0, 0, 0, 0)

def mzs(t1: Score, t2: Score) -> Score:
    # return Score(*map(sum, zip(t1, t2)))
    return Score(
        t1.accuracy  + t2.accuracy,
        t1.distance  + t2.distance,
        t1.length    + t2.length,
        t1.tagcount  + t2.tagcount,
    )


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
    pen_index = 0

    qix = 0
    hix = 0
    hlen = len(hay_segments)
    qlen = len(query_segments)

    # Pre-compute namespace colon index once instead of re-evaluating inside the loop
    try:
        colon_idx = hay_segments.index(":")
        ns_bonus = colon_idx + 1
        has_colon = True
    except ValueError:
        has_colon = False
        ns_bonus = 0
        colon_idx = 0

    while qix < qlen and hix < hlen:
        qseg = query_segments[qix]
        hseg = hay_segments[hix]

        scoredelta = compare_segments(qseg, hseg, query_split=query_split)

        if scoredelta == -1:
            hix += 1
            continue

        accuracy += scoredelta
        pen_index -= hix
        if has_colon:
            pen_index += ns_bonus

        qix += 1
        hix += 1

    if qix < qlen:
        return _SCORE_ZERO

    if has_colon:
        len_pen = sum(1 for h in hay_segments[colon_idx:] if len(h) > 1)
    else:
        len_pen = sum(1 for h in hay_segments if len(h) > 1)

    len_pen = max(0, len_pen-2) # Only penalize after 2+ segments

    return Score(accuracy=accuracy, distance=pen_index, length=-len_pen)


@functools.lru_cache(maxsize=64)
def _precompute_segments(
    collection: tuple[str, ...],
    query_split,
) -> dict[str, tuple[str, ...]]:
    """Return {hay: hay_segments} for the whole collection, computed once per
    (collection, query_split) pair.  For a stable collection this turns
    repeated per-item split_to_segments calls into a single dict lookup."""
    return {
        hay: split_to_segments(hay, query_split)
        for hay in collection
    }


def _merge_lists(
    *lists: list[tuple[Score, str]],
    edits: Sequence = (),
    count_tiebreak: None | Mapping[str, int] = None,
) -> list[tuple[Score, str]]:

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

    logger.debug(pprint.pformat(results))

    return results

def merge_lists(
    *lists: list[tuple[Score, str]],
    edits: Sequence = (),
    count_tiebreak: None | Mapping[str, int] = None,
) -> list[str]:
    results = _merge_lists(*lists, edits=edits, count_tiebreak=count_tiebreak)

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

    # if len(query) > 1:
    #     prior = perfect_search(
    #         collection,
    #         query[:-1],
    #         query_split,
    #         score_bonus,
    #         limit=limit
    #     )
    #     collection = tuple(hay for _, hay in prior)

    # Filter out
    query_segments: tuple[str, ...] = split_to_segments(query, query_split)

    query_segments = split_to_segments(query, query_split)
    hay_seg_map = _precompute_segments(collection, query_split)

    for hay in collection:
        if limit and len(results) >= limit:
            break

        if query == hay:
            score = Score(accuracy=100)
        else:
            score = score_segments(query_segments, hay_seg_map[hay], query_split=query_split)

        if score.accuracy < 1:
            continue

        if score_bonus:
            score = mzs(score, Score(accuracy=score_bonus))

        results.append((score, hay))

    return results