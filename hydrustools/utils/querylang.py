
import re
from typing import NewType, Sequence, TypeAlias

from hydrus_api.types import AndQuery, OrQuery, Query

# Copy-paste format used by hydrus client
MLQuery = NewType('MLQuery', str)

# Single line format used for query lang
SLQuery = NewType('SLQuery', str)

def parse_sl_query(query: SLQuery | str) -> Query:
    # Claude artifact
    def parse_token(token: str) -> 'str | OrQuery':
        token = token.strip()
        if token.startswith('(') and token.endswith(')'):
            inner = token[1:-1]
            return inner.split(' OR ')
        return token

    if not query.startswith('(') and not query.endswith(')'):
        if ' AND ' not in query and ' OR ' in query:
            return [query.split(' OR ')]

    parts = re.split(r'\s+AND\s+(?![^(]*\))', query)
    return [parse_token(p) for p in parts]

def parse_ml_query(query: MLQuery | str) -> Query:
    return [
        line if ' OR ' not in line
        else line.split(' OR ')
        for line in query.split("\n")
    ]

def serialize_query_sl(query: Query) -> SLQuery:
    return SLQuery(' AND '.join([
        pred if isinstance(pred, str)
        else "(" + " OR ".join(pred) + ")"
        for pred in query
    ]))

def serialize_query_ml(query: Query) -> MLQuery:
    return MLQuery('\n'.join([
        pred if isinstance(pred, str)
        else " OR ".join(pred)
        for pred in query
    ]))
