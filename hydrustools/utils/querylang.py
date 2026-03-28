
import logging
import re
from typing import NewType, Sequence, TypeAlias

from hydrus_api.types import AndQuery, OrQuery, Query

# Copy-paste format used by hydrus client
MLQuery = NewType('MLQuery', str)

# Single line format used for query lang
SLQuery = NewType('SLQuery', str)

logger = logging.getLogger(__name__)

def _is_wrapped_in_parens(query: str) -> bool:
    """Check if the entire query is wrapped in a single outer paren group."""
    if not (query.startswith('(') and query.endswith(')')):
        return False
    depth = 0
    for i, ch in enumerate(query):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if depth == 0 and i < len(query) - 1:
            return False  # outer parens closed before end
    return True

def parse_sl_query(
    query: SLQuery | str,
    tok_and='&&',
    tok_or='||'
) -> Query:
    if (tok_and not in " AND ") and (" AND " in query or " OR " in query):
        logger.debug("Switching to legacy sl parsing for %s", query)
        return parse_sl_query(
            query,
            tok_and='AND',
            tok_or='OR'
        )

    # Claude artifact
    def parse_token(token: str) -> 'str | OrQuery':
        token = token.strip()
        if token.startswith('(') and token.endswith(')'):
            inner = token[1:-1]
            return inner.split(f' {tok_or} ')
        return token

    if not _is_wrapped_in_parens(query):
        if f' {tok_and} ' not in query and f' {tok_or} ' in query:
            return [query.split(f' {tok_or} ')]

    parts = re.split(fr'\s+{tok_and}\s+(?![^(]*\))', query)
    return [parse_token(p) for p in parts]

def serialize_query_sl(
    query: Query,
    tok_and='&&',
    tok_or='||'
) -> SLQuery:
    return SLQuery(f' {tok_and} '.join([
        pred if isinstance(pred, str)
        else "(" + f' {tok_or} '.join(pred) + ")"
        for pred in query
    ]))

def parse_ml_query(
    query: MLQuery | str,
    # tok_and='AND',
    tok_or='OR'
) -> Query:
    return [
        line if f' {tok_or} ' not in line
        else line.split(f' {tok_or} ')
        for line in query.split("\n")
    ]

def serialize_query_ml(
    query: Query,
    # tok_and='AND',
    tok_or='OR'
) -> MLQuery:
    return MLQuery('\n'.join([
        pred if isinstance(pred, str)
        else f' {tok_or} '.join(pred)
        for pred in query
    ]))
