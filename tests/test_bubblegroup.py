import logging
import pprint
import random
import unittest
from functools import partial
from typing import Any

from hydrustools.cli import bubblegroup
from hydrustools.cli.bubblegroup import BubbleItem as BI
from hydrustools.cli.bubblegroup import BubbleSettings, bubble_group
from hydrustools.utils import htlogging

fs = frozenset

BS = partial(BubbleSettings, describe_moves=True)

def repr_groups(groups: dict[Any, list[BI]]):
    for key, itemlist in groups.items():
        pprint.pprint({key: [bi.tags for bi in itemlist]})

class TestBubbleGroup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        htlogging.configure_logging()
        bubblegroup.logger.setLevel(logging.DEBUG)

    def assertValueInGroup(self, groups: dict[frozenset, list[BI]], value: Any, key: set | frozenset):
        if isinstance(key, set):
            key = frozenset(key)
        self.assertIn(key, groups.keys())
        for k, l in groups.items():
            if k == key:
                self.assertIn(value, [bi.value for bi in l])

    def test_prefer_match_to_specific_group_member_is_subset_of(self):
        items = [
            BI(None, fs(('white', 2, 3))),
            BI(None, fs(('white', 2, 3))),

            BI(None, fs(('white',))),
            BI(None, fs(('white',))),

            BI(1, fs(('white', 2))),
        ]

        sorted = bubble_group(items, BS(min_size=2, max_size=4))

        repr_groups(sorted)

        self.assertValueInGroup(sorted, 1, {'white', 2, 3})

    def test_avoid_specific_utility_monster(self):
        pointer = BI(None, fs(('white', 2)))
        items = [
            BI(None, fs(('white', 'black', 'red', 1, 2, 3))),
            BI(None, fs(('white',))),

            BI(None, fs(('black',))),
            BI(None, fs(('red',))),

            pointer,
        ]

        sorted = bubble_group(items, BS(min_size=2, max_size=4))

        repr_groups(sorted)

        self.assertIn(pointer, sorted[frozenset({'white', 2})])

    def test_create_group_subsets(self):
        items = [
            BI(None, fs(('white', 1, 2,))),
            BI(None, fs(('white', 1, 3,))),
            BI(None, fs(('black', 4, 2,))),
            BI(None, fs(('black', 4, 3,))),
        ]

        sorted = bubble_group(items, BS(min_size=2, max_size=4))

        repr_groups(sorted)

        # self.assertIn(pointer, sorted[frozenset({'white', 2, 3})])

    def test_dont_overfill(self):
        items = [
            BI(None, fs(('white',1,))),
            BI(None, fs(('white',1,))),
            BI(None, fs(('black',1,))),
            BI(None, fs(('black',1,))),
            BI(None, fs(('red',1,))),
            BI(None, fs(('blue',1,))),
        ]

        sorted = bubble_group(items, BS(min_size=1, max_size=2))

        repr_groups(sorted)

        for list in sorted.values():
            self.assertLessEqual(len(list), 2)
        # self.assertIn(pointer, sorted[frozenset({'white', 2, 3})])

    def test_yahzee(self):
        sorted = bubble_group(
            [
                BI(i, fs((
                    random.choice('RGB'),
                    random.randint(1,6)
                )))
                for i in range(11)
            ],
            BS(min_size=2, max_size=3)
        )

        repr_groups(sorted)

        sorted = bubble_group(
            [
                BI(i, fs((
                    random.choice('♠♥♣♦'),
                    random.randint(1,12)
                )))
                for i in range(21)
            ],
            BS(min_size=3, max_size=5, expand_groups=False)
        )

        repr_groups(sorted)
