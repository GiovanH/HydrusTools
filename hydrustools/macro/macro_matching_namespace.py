from collections import Counter
import logging
import pprint
import re

from hydrustools.component.relationshipadderwin import RelationshipAction, RelationshipAdderWindow
from hydrustools.component.siblingadderwin import SiblingAction, SiblingAdderWindow

from .. import logic

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def tiformat(ti: logic.TagInfo):
    return f"{ti.value} ({ti.count})"

def run(tk=True):
    min_char_count = 10
    first_tag_factor = 10

    # max_page_size = 20

    all_tags = logic.search_tags_re(f"*", subpattern=None)
    all_tags_set = {ti.value for ti in all_tags}
    all_tags_map = {ti.value: ti for ti in all_tags}

    unnamespaced_tags = [t for t in all_tags_set if ':' not in t]
    sibling_resp = logic.get_sibling_ideal_targets(unnamespaced_tags)
    all_relationships: dict[str, logic.SiblingInfo] = {
         **{
            s: si
            for si in
            sibling_resp
            for s in si.siblings
        }
    }

    suggestions: list[RelationshipAction] = []

    for ut in unnamespaced_tags:
        if all_relationships[ut] and all_relationships[ut].ideal_tag != ut:
            continue
        spaced = ut.replace('_', ' ')
        scored = ut.replace(' ', '_')
        for maybe_better in {
            f'series:{spaced}',
            f'series:{scored}',
            f'character:{spaced}',
            f'character:{scored}',
            f'creator:{spaced}',
            f'creator:{scored}',
        }:
            if maybe_better in all_tags_set:
                ra = RelationshipAction(
                    ut,
                    maybe_better,
                    note=f"{tiformat(all_tags_map[ut])} → {tiformat(all_tags_map[maybe_better])}"
                )
                pprint.pprint(ra)
                suggestions.append(ra)

        # if len(suggestions) >= max_page_size:
        #     break


    RelationshipAdderWindow(suggestions)


if __name__ == "__main__":
    logic.init_client()
    run(tk=False)
