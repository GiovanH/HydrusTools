import logging
import pprint
import re
import threading

from hydrustools.utils import htlogging

from ..component.sibling_adder_window import SiblingAction, SiblingAdderWindow

from ..utils import hydrus

logger = logging.getLogger(__name__)


def find_localchars(tk=True):
    """The find_localchars macro searches all known character: tags for names that appear in different orders. It will group these by Series and collate them in a SiblingAdderWindow. Select the ideal version and the SiblingAdderWindow will export a relationship set.
    """
    char_parser = re.compile(r'^character:(?P<first>[a-z]+) (?P<last>[a-z]+)(?P<suffix> \([a-z]+\))?$')

    chars_with_spaces = hydrus.search_tags_re("character:*", r'.+ .+')

    matches = [
        f for f in
        (char_parser.match(c.value) for c in chars_with_spaces)
        if f
    ]
    matches.sort(key=lambda m: m.string)

    name_tuples = {
        (n['first'], n['last'])
        for n in
        (m.groupdict() for m in matches)
    }

    known_swapped_names = set()

    sibling_actions: list[SiblingAction] = []

    sibling_resp = hydrus.get_relationship_info([f"{m.string}" for m in matches])
    sibling_info: dict[str, hydrus.RelationshipInfo] = {
        **{
            si.tag: si
            for si in
            sibling_resp
        },
        **{
            s: si
            for si in
            sibling_resp
            for s in si.siblings
        }
    }
    # pprint.pprint(sibling_info)

    for m in matches:
        n = m.groupdict()
        name = (n['first'], n['last'])
        swapped = (n['last'], n['first'])

        if name == swapped:
            continue

        if swapped in name_tuples:
            if swapped in known_swapped_names:
                continue

            tag = m.string
            sibling_options = [
                f"character:{n['first']} {n['last']}{n['suffix'] or ''}",
                f"character:{n['last']} {n['first']}{n['suffix'] or ''}"
            ]
            # current_sibling = None

            group = ""

            si: hydrus.RelationshipInfo | None = sibling_info.get(tag)
            if si:
                # print(si)
                # current_sibling = sibling_options.index(si.ideal_tag)
                # tag = si.ideal_tag
                logger.info(si)

                group = ' '.join(si.ancestors)

            action = SiblingAction(tag, sibling_options, group)

            logger.info(action)


            sibling_actions.append(action)

            known_swapped_names.add(name)


    # print()
    # logger.info(f"{name_tuples}")



    SiblingAdderWindow(sibling_actions)

def start():
    thread = threading.Thread(target=find_localchars)
    thread.start()


if __name__ == "__main__":
    hydrus.init_client()
    htlogging.configure_logging()
    find_localchars(tk=False)
