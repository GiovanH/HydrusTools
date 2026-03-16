import unittest

from hydrustools.lookup.registry import MetadataActions, postprocessSuggestions
from hydrustools.utils import htlogging


class TestPostprocessSuggestions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        htlogging.configure_logging()

    def test_parse(self):
        pass