import logging
import pprint
import unittest
from typing import Any

from hydrustools.utils import htlogging
from hydrustools.cli import bubblegroup
from hydrustools.cli.bubblegroup import BubbleItem as BI
from hydrustools.cli.bubblegroup import bubble_group

fs = frozenset

def repr_groups(groups: dict[Any, list[BI]]):
    for key, itemlist in groups.items():
        print(key)
        pprint.pprint(itemlist)

class TestBubbleGroup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        htlogging.configure_logging()
        bubblegroup.logger.setLevel(logging.DEBUG)

    def notest_prefer_match_to_specific_group_member_is_subset_of(self):
        pointer = BI(None, fs(('white', 2)))
        items = [
            BI(None, fs(('white', 2, 3))),
            BI(None, fs(('white', 2, 3))),

            BI(None, fs(('white',))),
            BI(None, fs(('white',))),

            pointer,
        ]

        sorted = bubble_group(items, min_size=2, max_size=4)

        repr_groups(sorted)

        self.assertIn(pointer, sorted[frozenset({'white', 2, 3})])

    def notest_avoid_specific_utility_monster(self):
        pointer = BI(None, fs(('white', 2)))
        items = [
            BI(None, fs(('white', 'black', 'red', 1, 2, 3))),
            BI(None, fs(('white',))),

            BI(None, fs(('black',))),
            BI(None, fs(('red',))),

            pointer,
        ]

        sorted = bubble_group(items, min_size=2, max_size=4)

        repr_groups(sorted)

        self.assertIn(pointer, sorted[frozenset({'white', 2, 3})])

    def notest_create_group_subsets(self):
        items = [
            BI(None, fs(('white', 1, 2,))),
            BI(None, fs(('white', 1, 3,))),
            BI(None, fs(('black', 4, 2,))),
            BI(None, fs(('black', 4, 3,))),
        ]

        sorted = bubble_group(items, min_size=2, max_size=4)

        repr_groups(sorted)

        # self.assertIn(pointer, sorted[frozenset({'white', 2, 3})])