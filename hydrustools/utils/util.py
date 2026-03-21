from contextlib import contextmanager
from typing import Any, Callable, Generator, Iterable, TypeVar
import logging

T = TypeVar('T')

logger = logging.getLogger(__name__)

@contextmanager
def timer(label="task", logger: Callable[[str], None] = logger.info, min_secs: float = 1):
    """Times a code block and prints time taken to screen

    Args:
        label (str, optional): Description of task
    """
    import time
    start_time = time.time()

    try:
        yield
    finally:
        time_taken = time.time() - start_time
        if time_taken > min_secs:
            logger(f"Processed {label} in {time_taken} secs")


def chunk(iterable: Iterable[T], maxsize: int) -> Generator[tuple[T, ...], Any, None]:
    """A generator that yields lists of size `maxsize` containing the results of iterable `it`.

    Args:
        iterable: An iterable to split into chunks
        maxsize (int): Max size of chunks

    Yields:
        lists of size [1, maxsize]

    >>> list(chunk(range(10), 4))
    [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9)]
    """
    from itertools import islice

    iter_it = iter(iterable)
    yield from iter(lambda: tuple(islice(iter_it, maxsize)), ())
