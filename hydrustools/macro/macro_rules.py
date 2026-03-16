import json
import logging
import re
import threading
from pathlib import Path

import hydrus_api
import tqdm

import hydrustools.utils.util
from hydrustools.utils import htlogging, querylang

from ..utils import hydrus

logger = logging.getLogger(__name__)

delete_tags = [
    'creator:unsorted',
    'meta:badtag'
]

def run(tk=True):
    for tag_name in delete_tags:
        logger.info(f"Deleting tag {tag_name}")
        try:
            hydrus.replace_tag(tag_name, [])
        except hydrus_api.MissingParameter:
            logger.info("Nothing to do!")

if __name__ == "__main__":
    hydrus.init_client()
    htlogging.configure_logging()
    hydrus.logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    run(tk=False)
