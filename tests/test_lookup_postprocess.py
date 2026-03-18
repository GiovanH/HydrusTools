import logging
import unittest
from unittest.mock import patch

from hydrustools.lookup.registry import MetadataActions, postprocessSuggestions
from hydrustools.utils.hydrus import FileMetadata

logger = logging.getLogger(__name__)

# Claude tests

def _image(file_id=1, known_urls=None, tags=None) -> FileMetadata:
    """Helper: build a minimal FileMetadata dict."""
    return {
        "file_id": file_id,
        "known_urls": known_urls or [],
        "_tags": tags or [],  # type: ignore
    }


class TestMetadataActionsHasAny(unittest.TestCase):
    def test_all_none_returns_false(self):
        ma = MetadataActions(file_id=1)
        self.assertFalse(ma.has_any())

    def test_all_empty_lists_returns_false(self):
        ma = MetadataActions(
            file_id=1,
            add_tags=[],
            add_downloader_tags=[],
            add_urls=[],
            add_notes=[],
            info_only=[],
        )
        self.assertFalse(ma.has_any())

    def test_add_tags_populated_returns_true(self):
        ma = MetadataActions(file_id=1, add_tags=["character:foo"])
        self.assertTrue(ma.has_any())

    def test_add_downloader_tags_populated_returns_true(self):
        ma = MetadataActions(file_id=1, add_downloader_tags=["artist:bar"])
        self.assertTrue(ma.has_any())

    def test_add_urls_populated_returns_true(self):
        ma = MetadataActions(file_id=1, add_urls=["https://example.com"])
        self.assertTrue(ma.has_any())

    def test_add_notes_populated_returns_true(self):
        ma = MetadataActions(file_id=1, add_notes=[{"title": "note", "content": "x"}])
        self.assertTrue(ma.has_any())

    def test_info_only_populated_returns_true(self):
        ma = MetadataActions(file_id=1, info_only=["some:tag"])
        self.assertTrue(ma.has_any())


class TestMetadataActionsRemainingFor(unittest.TestCase):
    def setUp(self):
        # Use patch() so this works whether hydrus is a real module or a stub.
        # The patch is started here and stopped in tearDown, giving each test
        # a fresh MagicMock with no leftover side_effect or return_value state.
        self._patcher = patch("hydrustools.utils.hydrus.local_tags", return_value=[])
        self.mock_local_tags = self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_raises_on_mismatched_file_id(self):
        ma = MetadataActions(file_id=1, add_tags=["a:b"])
        with self.assertRaises(ValueError):
            ma.remaining_for(_image(file_id=99))

    def test_tags_already_present_are_removed(self):
        self.mock_local_tags.return_value = ["character:alice"]
        ma = MetadataActions(file_id=1, add_tags=["character:alice", "character:bob"])
        result = ma.remaining_for(_image(file_id=1))
        self.assertNotIn("character:alice", result.add_tags)
        self.assertIn("character:bob", result.add_tags)

    def test_all_tags_already_present_returns_none(self):
        self.mock_local_tags.return_value = ["character:alice"]
        ma = MetadataActions(file_id=1, add_tags=["character:alice"])
        result = ma.remaining_for(_image(file_id=1))
        self.assertIsNone(result.add_tags)

    def test_urls_already_present_are_removed(self):
        existing_url = "https://example.com/image.jpg"
        ma = MetadataActions(
            file_id=1,
            add_urls=[existing_url, "https://new.example.com/other.jpg"],
        )
        result = ma.remaining_for(_image(file_id=1, known_urls=[existing_url]))
        self.assertNotIn(existing_url, result.add_urls)
        self.assertIn("https://new.example.com/other.jpg", result.add_urls)

    def test_all_urls_already_present_returns_none(self):
        url = "https://example.com/image.jpg"
        ma = MetadataActions(file_id=1, add_urls=[url])
        result = ma.remaining_for(_image(file_id=1, known_urls=[url]))
        self.assertIsNone(result.add_urls)

    def test_no_tags_to_subtract_keeps_all(self):
        # default return_value=[] means nothing is subtracted
        ma = MetadataActions(file_id=1, add_tags=["character:alice"])
        result = ma.remaining_for(_image(file_id=1))
        self.assertIn("character:alice", result.add_tags)

    def test_notes_and_info_only_are_preserved_unchanged(self):
        ma = MetadataActions(
            file_id=1,
            add_notes=[{"title": "n", "content": "v"}],
            info_only=["meta:info"],
        )
        result = ma.remaining_for(_image(file_id=1))
        self.assertEqual(result.add_notes, [{"title": "n", "content": "v"}])
        self.assertEqual(result.info_only, ["meta:info"])

    def test_downloader_tags_already_present_are_removed(self):
        # First call (local tags) returns empty; second call (downloader tags) returns the tag
        self.mock_local_tags.side_effect = [[], ["artist:bob"]]
        ma = MetadataActions(file_id=1, add_downloader_tags=["artist:bob", "artist:carol"])
        result = ma.remaining_for(_image(file_id=1))
        self.assertNotIn("artist:bob", result.add_downloader_tags)
        self.assertIn("artist:carol", result.add_downloader_tags)


class TestPostprocessSuggestionsUnderscores(unittest.TestCase):
    def test_underscores_replaced_when_flag_set(self):
        ma = MetadataActions(file_id=1, add_tags=["character:big_ears"])
        result = postprocessSuggestions(ma, underscores_to_spaces=True)
        self.assertIn("character:big ears", result.add_tags)
        self.assertNotIn("character:big_ears", result.add_tags)

    def test_underscores_kept_when_flag_not_set(self):
        ma = MetadataActions(file_id=1, add_tags=["character:big_ears"])
        result = postprocessSuggestions(ma, underscores_to_spaces=False)
        self.assertIn("character:big_ears", result.add_tags)


class TestPostprocessSuggestionsWhitelist(unittest.TestCase):
    def test_tags_not_in_whitelist_are_removed(self):
        ma = MetadataActions(file_id=1, add_tags=["character:alice", "meta:info", "rating:safe"])
        result = postprocessSuggestions(ma, tag_namespace_whitelist=["character", "rating"])
        self.assertIn("character:alice", result.add_tags)
        self.assertIn("rating:safe", result.add_tags)
        self.assertNotIn("meta:info", result.add_tags)

    def test_all_tags_filtered_when_none_match_whitelist(self):
        ma = MetadataActions(file_id=1, add_tags=["meta:x", "meta:y"])
        result = postprocessSuggestions(ma, tag_namespace_whitelist=["character"])
        self.assertEqual(result.add_tags, [])

    def test_empty_whitelist_keeps_all_tags(self):
        ma = MetadataActions(file_id=1, add_tags=["meta:x", "character:y"])
        result = postprocessSuggestions(ma, tag_namespace_whitelist=None)
        self.assertIn("meta:x", result.add_tags)
        self.assertIn("character:y", result.add_tags)

    def test_tag_without_colon_removed_when_whitelist_active(self):
        ma = MetadataActions(file_id=1, add_tags=["bare_tag", "character:alice"])
        result = postprocessSuggestions(ma, tag_namespace_whitelist=["character"])
        self.assertNotIn("bare_tag", result.add_tags)
        self.assertIn("character:alice", result.add_tags)


class TestPostprocessSuggestionsMinCountLocal(unittest.TestCase):
    def test_low_count_tag_moved_to_downloader_tags(self):
        ma = MetadataActions(file_id=1, add_tags=["character:rare"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=10,
            tag_count_cache={"character:rare": 2},
        )
        self.assertNotIn("character:rare", result.add_tags or [])
        self.assertIn("character:rare", result.add_downloader_tags)

    def test_high_count_tag_stays_local(self):
        ma = MetadataActions(file_id=1, add_tags=["character:common"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=10,
            tag_count_cache={"character:common": 50},
        )
        self.assertIn("character:common", result.add_tags)
        self.assertListEqual(result.add_downloader_tags, [])

    def test_tag_missing_from_cache_treated_as_zero(self):
        ma = MetadataActions(file_id=1, add_tags=["character:unknown"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=1,
            tag_count_cache={},
        )
        self.assertNotIn("character:unknown", result.add_tags or [])
        self.assertIn("character:unknown", result.add_downloader_tags)

    def test_always_local_namespace_not_moved(self):
        ma = MetadataActions(file_id=1, add_tags=["creator:bigartist"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=100,
            tag_count_cache={"creator:bigartist": 0},
            always_local_namespaces=["creator"],
        )
        self.assertIn("creator:bigartist", result.add_tags)
        self.assertListEqual(result.add_downloader_tags, [])

    def test_blacklisted_tag_moved_regardless_of_count(self):
        ma = MetadataActions(file_id=1, add_tags=["character:banned"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=1,
            tag_count_cache={"character:banned": 999},
            blacklist_tags_from_local=["character:banned"],
        )
        self.assertNotIn("character:banned", result.add_tags or [])
        self.assertIn("character:banned", result.add_downloader_tags)

    def test_existing_downloader_tags_extended(self):
        ma = MetadataActions(
            file_id=1,
            add_tags=["character:rare"],
            add_downloader_tags=["artist:existing"],
        )
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=10,
            tag_count_cache={"character:rare": 1},
        )
        self.assertIn("artist:existing", result.add_downloader_tags)
        self.assertIn("character:rare", result.add_downloader_tags)


class TestPostprocessSuggestionsMinCountDownload(unittest.TestCase):
    def test_low_count_downloader_tag_moved_to_info_only(self):
        ma = MetadataActions(file_id=1, add_downloader_tags=["character:very_rare"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_download=5,
            tag_count_cache={"character:very_rare": 1},
        )
        self.assertNotIn("character:very_rare", result.add_downloader_tags or [])
        self.assertIn("character:very_rare", result.info_only)

    def test_sufficient_count_downloader_tag_stays(self):
        ma = MetadataActions(file_id=1, add_downloader_tags=["character:okay"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_download=5,
            tag_count_cache={"character:okay": 10},
        )
        self.assertIn("character:okay", result.add_downloader_tags)
        self.assertListEqual(result.info_only, [])

    def test_existing_info_only_extended(self):
        ma = MetadataActions(
            file_id=1,
            add_downloader_tags=["character:very_rare"],
            info_only=["meta:existing"],
        )
        result = postprocessSuggestions(
            ma,
            tags_min_count_download=5,
            tag_count_cache={"character:very_rare": 0},
        )
        self.assertIn("meta:existing", result.info_only)
        self.assertIn("character:very_rare", result.info_only)


class TestPostprocessSuggestionsChaining(unittest.TestCase):
    """Tags can cascade: local → downloader → info_only in one pass."""

    def test_tag_cascades_from_local_to_info_only(self):
        # add_tags has a rare tag that should go to downloader,
        # but downloader threshold also too high → should land in info_only
        ma = MetadataActions(file_id=1, add_tags=["character:ghost"])
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=10,
            tags_min_count_download=10,
            tag_count_cache={"character:ghost": 0},
        )
        self.assertNotIn("character:ghost", result.add_tags or [])
        # The tag was moved to add_downloader_tags THEN evaluated against
        # tags_min_count_download in the same call.
        self.assertIn("character:ghost", result.info_only)
        self.assertNotIn("character:ghost", result.add_downloader_tags or [])

    def test_no_tags_returns_unchanged(self):
        ma = MetadataActions(file_id=1)
        result = postprocessSuggestions(
            ma,
            tags_min_count_local=10,
            tags_min_count_download=10,
        )
        self.assertListEqual([], result.add_tags)
        self.assertListEqual([], result.add_downloader_tags)
        self.assertListEqual([], result.info_only)
