# noqa: UP045
import typing as T
from collections import abc

import hydrus_api
from hydrus_api import FileSortType

from hydrustools.utils import querylang


class TypedClient(hydrus_api.Client):
    def search_files( # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        tags: querylang.Query,
        file_service_keys: T.Optional[abc.Iterable[T.Union[str, abc.Iterable[str]]]] = None,
        deleted_file_service_keys: T.Optional[abc.Iterable[str]] = None,
        tag_service_key: T.Optional[str] = None,
        file_sort_type: T.Optional[T.Union[int, FileSortType]] = None,
        file_sort_asc: T.Optional[bool] = None,
        return_file_ids: T.Optional[bool] = None,
        return_hashes: T.Optional[bool] = None,
        include_current_tags: T.Optional[bool] = None,
        include_pending_tags: T.Optional[bool] = None,
    ) -> dict[str, T.Any]:
        return super().search_files(
            tags=tags, # type: ignore
            file_service_keys=file_service_keys,
            deleted_file_service_keys=deleted_file_service_keys,
            tag_service_key=tag_service_key,
            file_sort_type=file_sort_type,
            file_sort_asc=file_sort_asc,
            return_file_ids=return_file_ids,
            return_hashes=return_hashes,
            include_current_tags=include_current_tags,
            include_pending_tags=include_pending_tags
        )
