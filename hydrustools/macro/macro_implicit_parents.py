from collections import Counter
import logging
import pprint

import tqdm
from tqdm.tk import tqdm as tqdmtk

from hydrustools.component.relationshipadderwin import RelationshipAction, RelationshipAdderWindow

from .. import logic

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def run(tk=True):
    tqdm_iterator = (tqdmtk if tk else tqdm.tqdm)

    min_char_count = 10
    first_tag_factor = 10
    namespace_a = "character:"
    namespace_b = "series:"
    # namespace_a = ""
    # namespace_b = ""
    max_page_size = 20

    all_characters = logic.search_tags_re(f"{namespace_a}*", subpattern=rf"^{namespace_a}.*")

    sibling_resp = logic.get_sibling_ideal_targets([t.value for t in all_characters])
    all_relationships: dict[str, logic.SiblingInfo] = {
         **{
            s: si
            for si in
            sibling_resp
            for s in si.siblings
        }
    }

    # pprint.pprint(all_characters)
    # pprint.pprint(relationships)
    orphans = []

    for ci in all_characters:
        # if not ci.value.startswith("character:"):
        #     continue

        if ci.count < min_char_count:
            logger.debug(f"Skipping tag {ci} without {min_char_count} occurrences")
            continue

        si = all_relationships.get(ci.value)
        if not si:
            logger.info(f"Adding tag {ci.value} with no relationship data")
            orphans.append(ci.value)
            continue
        if ci.value != si.ideal_tag:
            logger.debug(f"Skipping non-ideal tag {ci.value} in {si}")
            continue
        if len(si.ancestors) > 0:
            if namespace_b and any(a.startswith(namespace_b) for a in si.ancestors):
                logger.info(f"Skipping tag {ci.value} with known series parent in {si.ancestors}")
                continue
            logger.info(f"Adding known orphan tag {ci.value} with of {si}")
            orphans.append(ci.value)

    suggestions: list[RelationshipAction] = []

    for char in tqdm_iterator(orphans):
        si = all_relationships.get(char)
        my_counter = Counter()

        logger.info(f"No parent series for {char!r} in {si}")
        # logger.info(f"Searched {pprint.pformat(all_relationships)}")

        resp = logic.client.search_files(
            tags=[char]
        )
        file_ids = resp['file_ids']
        metadata = logic.client.get_file_metadata(file_ids=file_ids)['metadata']

        for file in metadata:
            try:
                local_display_tags = file['tags'][logic.local_tags_service_key]['display_tags']
                if local_display_tags == {}:
                    continue

                file_tags = local_display_tags['0']
                my_counter.update(
                    [
                        t for t in file_tags
                        if t.startswith(namespace_b)
                        and t != char
                        and (not si or t not in si.ancestors)
                        and (not si or t not in si.descendants)
                    ]
                )
            except KeyError:
                pprint.pprint(object=file)
                raise

        new_tag = None

        logger.info(f"Should we suggest adding a parent to {char} from {my_counter}?")
        if len(my_counter.keys()) == 0:
            logger.info("No, empty.")
            continue
        if len(my_counter.keys()) == 1:
            logger.info("Yes, only one option")
            new_tag = [*my_counter.keys()][0]
        if len(my_counter.keys()) >= 2:
            first, second, *etc = [*my_counter.keys()]
            logger.info(f"{first} has {my_counter[first]}, {second} has {my_counter[second]}")
            if my_counter[first] >= my_counter[second] * first_tag_factor:
                logger.info(f"Recognizing {first} as the true parent")
                new_tag = first
            else:
                continue
        if not new_tag:
            continue

        ra = RelationshipAction(
            char,
            new_tag,
            note=repr(my_counter)
        )
        pprint.pprint(ra)
        suggestions.append(ra)

        if len(suggestions) >= max_page_size:
            break


    RelationshipAdderWindow(suggestions)

if __name__ == "__main__":
    logic.init_client()
    run(tk=False)
