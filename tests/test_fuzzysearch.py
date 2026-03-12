import logging
from typing import Sequence
import unittest

from hydrustools import htlogging
from hydrustools.component import fuzzysearch

TAGS = (
    "steven universe",
    "series:steven universe",
    "character:amethyst (steven universe)",
    "character:aquamarine (steven universe)",
    "character:bismuth (steven universe)",
    "character:blue diamond (steven universe)",
    "character:blue diamond",
    "character:connie maheswaran",
    "character:famethyst (steven universe)",
    "character:garnet (steven universe)",
    "character:greg universe",
    "character:holly blue agate (steven universe)",
    "character:holo-pearl",
    "character:jasper (steven universe)",
    "character:jay-ten (steven universe)",
    "character:kevin (steven universe)",
    "character:lapis lazuli (steven universe)",
    "character:lars (steven universe)",
    "character:mystery girl (steven universe)",
    "character:opal (fusion)",
    "character:original character (gem)",
    "character:padparadscha",
    "character:pearl (steven universe)",
    "character:peridot (steven universe)",
    "character:peridot",
    "character:pink diamond",
    "character:pink pearl (steven universe)",
    "character:pink steven",
    "character:priyanka maheswaran",
    "character:purple pearl (steven universe)",
    "character:rose quartz",
    "character:ruby (steven universe)",
    "character:ruby eyeball",
    "character:sadie miller (steven universe)",
    "character:sapphire (steven universe)",
    "character:skinny jasper",
    "character:spinel",
    "character:steven quartz universe",
    "character:stevonnie",
    "character:sugilite",
    "character:topaz (steven universe)",
    "character:white diamond (steven universe)",
    "character:white diamond",
    "character:white pearl (steven universe)",
    "character:wy-six (steven universe)",
    "character:yellow diamond",
)

class TestFuzzySearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        htlogging.configure_logging()
        fuzzysearch.logger.setLevel(logging.DEBUG)

    def assertBefore(self, matches: Sequence[str], item1: str, item2: str):

        self.assertIn(item1, matches)
        self.assertIn(item2, matches)
        self.assertLess(
            matches.index(item1),
            matches.index(item2)
        )

    def test_search_basic(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "rub"
        ))
        self.assertIn("character:ruby (steven universe)", matches)
        self.assertNotIn("character:white diamond", matches)

    def test_search_offset(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "steven"
        ))
        self.assertIn("steven universe", matches)
        self.assertIn("series:steven universe", matches)

    def test_search_context(self):
        PEARLS = tuple(t for t in TAGS if "pearl" in t)
        matches = fuzzysearch.merge_lists(
            fuzzysearch.perfect_search(
                PEARLS,
                "pink",
                score_bonus=10
            ),
            fuzzysearch.perfect_search(
                TAGS,
                "pink"
            )
        )
        self.assertBefore(matches,
            "character:pink pearl (steven universe)",
            "character:pink diamond"
        )

        DIAMONDS = tuple(t for t in TAGS if "diamond" in t)
        matches = fuzzysearch.merge_lists(
            fuzzysearch.perfect_search(
                DIAMONDS,
                "pink",
                score_bonus=10
            ),
            fuzzysearch.perfect_search(
                TAGS,
                "pink"
            )
        )
        self.assertBefore(matches,
            "character:pink diamond",
            "character:pink pearl (steven universe)"
        )

    def test_search_limit(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "steven"
        ))
        self.assertGreater(len(matches), 10)

        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "steven",
            limit=5
        ))
        self.assertLess(len(matches), 10)

    def test_search_basic_prefer_concise(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "steven"
        ))
        self.assertIn("steven universe", matches)
        self.assertIn("series:steven universe", matches)

        self.assertLess(
            matches.index("steven universe"),
            matches.index("series:steven universe")
        )

        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "jasper"
        ))
        self.assertBefore(matches,
            "character:jasper (steven universe)",
            "character:skinny jasper"
        )


    def test_search_segments_basic(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "w d"
        ))
        self.assertIn("character:white diamond", matches)

    def test_search_segments_skip(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "st u"
        ))

        print(matches)

        self.assertIn("character:steven quartz universe", matches)

        self.assertIn("character:wy-six (steven universe)", matches)
        self.assertIn("character:amethyst (steven universe)", matches)

        self.assertLess(
            matches.index("character:steven quartz universe"),
            matches.index("character:wy-six (steven universe)")
        )

        self.assertLess(
            matches.index("character:steven quartz universe"),
            matches.index("character:amethyst (steven universe)")
        )

    def test_search_segments_include_all(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "pea"
        ))
        self.assertIn("character:pearl (steven universe)", matches)
        self.assertIn("character:white pearl (steven universe)", matches)
        self.assertIn("character:holo-pearl", matches)

        self.assertLess(
            matches.index("character:pearl (steven universe)"),
            matches.index("character:white pearl (steven universe)")
        )

    def test_search_segments_bonus_match(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            tuple([*TAGS, "character:sweet pea"]),
            "pea"
        ))
        self.assertBefore(matches,
            "character:sweet pea",
            "character:pearl (steven universe)"
        )

    def test_search_match_split(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "gem"
        ))
        self.assertIn("character:original character (gem)", matches)

    def test_search_extra(self):
        extras = (
            "-series:steven universe",
        )
        matches = fuzzysearch.merge_lists(
            fuzzysearch.perfect_search(
                extras,
                "st u"
            ),
            fuzzysearch.perfect_search(
                TAGS,
                "st u",
            )
        )
        self.assertIn("-series:steven universe", matches)

    def test_search_consume_whole_query(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "ser:st u",
        ))
        self.assertIn("series:steven universe", matches)
        self.assertNotIn("steven universe", matches)

        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "st ur",
        ))
        self.assertNotIn("steven universe", matches)

        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "st u v",
        ))
        self.assertNotIn("steven universe", matches)


    def test_search_filter_split(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            TAGS,
            "-p"
        ))
        self.assertIn("character:holo-pearl", matches)

        # self.assertIn("character:pearl (steven universe)", matches)

        # self.assertLess(
        #     matches.index("character:holo-pearl"),
        #     matches.index("character:pearl (steven universe)")
        # )

    # TODO: prioritize context even with limits

    def test_search_filter_context_priority(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            ("fantasy", "your fantroll"),
            "fant"
        ))
        self.assertBefore(matches,
            "fantasy",
            "your fantroll"
        )
        matches = fuzzysearch.merge_lists(
            fuzzysearch.perfect_search(
                ("your fantroll",),
                "fant",
                score_bonus=10
            ),
            fuzzysearch.perfect_search(
                ("fantasy", "your fantroll"),
                "fant",
            )
        )
        self.assertBefore(matches,
            "your fantroll",
            "fantasy",
        )

    def test_optional_punctuation(self):
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            ("high-tech",),
            "hi-t"
        ))
        self.assertIn("high-tech", matches)
        matches = fuzzysearch.merge_lists(fuzzysearch.perfect_search(
            ("low-tech",),
            "low tech"
        ))
        self.assertIn("low-tech", matches)
