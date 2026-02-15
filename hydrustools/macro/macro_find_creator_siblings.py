import logging
import pprint
import threading

import tqdm
from tqdm.tk import tqdm as tqdmtk

from hydrustools import htlogging

from ..component.relationship_adder import RelationshipAction, RelationshipAdderWindow

from .. import logic

logger = logging.getLogger(__name__)


def tiformat(ti: logic.TagInfo):
    return f"{ti.value} ({ti.count})"

def run(tk=True):
    tqdm_iterator = (tqdmtk if tk else tqdm.tqdm)

    min_char_count = 10
    first_tag_factor = 10

    # max_page_size = 20

    all_tags = logic.search_tags_re("creator:", subpattern=None)
    all_tags_set = {ti.value for ti in all_tags}
    all_tags_map = {ti.value: ti for ti in all_tags}

    sibling_resp = logic.get_sibling_ideal_targets([*all_tags_set])
    all_relationships: dict[str, logic.SiblingInfo] = {
         **{
            s: si
            for si in
            sibling_resp
            for s in si.siblings
        }
    }

    suggestions: list[RelationshipAction] = []

    iterable = tqdm_iterator(all_tags_set, leave=False)
    for ut in iterable:
        if all_relationships[ut] and all_relationships[ut].ideal_tag != ut:
            # Already pointing to a sibling
            continue

        handle_ver = f"{ut}.bsky.social"
        if handle_ver in all_tags_set:
            ra = RelationshipAction(
                handle_ver,
                ut,
                note=f"{tiformat(all_tags_map[handle_ver])} → {tiformat(all_tags_map[ut])}"
            )
            pprint.pprint(ra)
            suggestions.append(ra)

    if isinstance(iterable, tqdmtk):
        iterable.leave = False
        iterable.close()

    RelationshipAdderWindow(suggestions)

def start():
    thread = threading.Thread(target=run)
    thread.start()


if __name__ == "__main__":
    logic.init_client()
    run(tk=False)
