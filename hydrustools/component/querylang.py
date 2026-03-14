
from typing import TypeAlias

AndQuery: TypeAlias = list['str | OrQuery']
OrQuery: TypeAlias = list['str | OrQuery']
Query = AndQuery

def parse_ml_query(query: str) -> Query:
    return query.split("\n") # type: ignore

def parse_sl_query(query: str) -> Query:
    return query.split(' AND ') # type: ignore

def serialize_query_sl(query: Query) -> str:
    # return query.split(' AND ')
    raise NotImplementedError

def serialize_query_ml(query: Query) -> str:
    # return query.split(' AND ')
    raise NotImplementedError
