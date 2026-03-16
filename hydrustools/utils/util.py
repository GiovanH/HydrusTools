from contextlib import contextmanager
from typing import Callable
import logging

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
        yield None
    finally:
        time_taken = time.time() - start_time
        if time_taken > min_secs:
            logger(f"Processed {label} in {time_taken} secs")
