
from dataclasses import dataclass
import functools
import itertools
import re
from typing import Any, Callable, Optional, Sequence

# TODO: Better fuzzy searching
# TODO: Use - in entry to remove tags

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
    """
    >>> getMatches("dav ja", collection)
    MatchResults(all=[], resolved=None, unique=False)
    >>> getMatches("ri j", collection, fuzzy=True)
    MatchResults(all=['vris john'], resolved='vris john', unique=True)
    >>> getMatches("jo", collection)
    MatchResults(all=['john', 'john rose'], resolved='john', unique=False)

    >>> getMatches("john", collection).resolved
    'john'
    >>> getMatches("john", collection).all
    ['john', 'john rose']

    >>> getMatches("-john", collection).resolved
    'vris john'
    >>> getMatches("-rose", collection).resolved
    'john rose'

    >>> getMatches("jo ro", collection).resolved
    'john rose'
    """
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
                    print(item, item_segs, zipped)
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

