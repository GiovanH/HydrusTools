import logging
import unittest

from hydrustools.utils import htlogging, querylang
from hydrustools.utils.querylang import MLQuery, SLQuery


class TestQueryLang(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        htlogging.configure_logging()
        logging.getLogger('utils.querylang').setLevel(logging.DEBUG)

    def test_parse_sl_base(self):
        querystr = SLQuery("tag1")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            ['tag1']
        )

    def test_parse_sl_split(self):
        querystr = SLQuery("tag1 && tag2")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            ['tag1', 'tag2']
        )

    def test_parse_sl_just_ors(self):
        querystr = SLQuery("(tag2 || tag3)")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['tag2', 'tag3']]
        )

    def test_parse_sl_just_ors_noparens(self):
        querystr = SLQuery("tag2 || tag3")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['tag2', 'tag3']]
        )

    def test_parse_sl_just_ors_unbalanced_parens(self):
        querystr = SLQuery("character:caliborn || character:calliope (homestuck)")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['character:caliborn', 'character:calliope (homestuck)']]
        )

    def test_parse_sl_ors_unbalanced_parens(self):
        querystr = SLQuery("(character:caliborn || character:calliope (homestuck))")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['character:caliborn', 'character:calliope (homestuck)']]
        )

    def test_parse_sl_split_or(self):
        querystr = SLQuery("tag1 && (tag2 || tag3)")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            ['tag1', ['tag2', 'tag3']]
        )

    def test_parse_ml_split(self):
        querystr = MLQuery("tag1\ntag2")
        self.assertEqual(
            querylang.parse_ml_query(querystr),
            ['tag1', 'tag2']
        )

    def test_parse_ml_split_or(self):
        querystr = MLQuery("tag1\ntag2 OR tag3")
        self.assertEqual(
            querylang.parse_ml_query(querystr),
            ['tag1', ['tag2', 'tag3']]
        )

    def test_serialize_sl(self):
        query: querylang.AndQuery = ['tag1', 'tag2']
        self.assertEqual(
            querylang.serialize_query_sl(query),
            "tag1 && tag2"
        )

    def test_serialize_sl_or(self):
        query: querylang.AndQuery = ['tag1', ['tag2', 'tag3']]
        self.assertEqual(
            querylang.serialize_query_sl(query),
            "tag1 && (tag2 || tag3)"
        )

    def test_serialize_ml(self):
        query: querylang.AndQuery = ['tag1', 'tag2']
        self.assertEqual(
            querylang.serialize_query_ml(query),
            "tag1\ntag2"
        )

    def test_serialize_ml_or(self):
        query: querylang.AndQuery = ['tag1', ['tag2', 'tag3']]
        self.assertEqual(
            querylang.serialize_query_ml(query),
            querylang.MLQuery("tag1\ntag2 OR tag3")
        )


class TestQueryLangLegacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        htlogging.configure_logging()
        logging.getLogger('utils.querylang').setLevel(logging.DEBUG)

    def test_parse_sl_split(self):
        querystr = SLQuery("tag1 AND tag2")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            ['tag1', 'tag2']
        )

    def test_parse_sl_just_ors(self):
        querystr = SLQuery("(tag2 OR tag3)")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['tag2', 'tag3']]
        )

    def test_parse_sl_just_ors_noparens(self):
        querystr = SLQuery("tag2 OR tag3")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['tag2', 'tag3']]
        )

    def test_parse_sl_just_ors_unbalanced_parens(self):
        querystr = SLQuery("character:caliborn OR character:calliope (homestuck)")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['character:caliborn', 'character:calliope (homestuck)']]
        )

    def test_parse_sl_ors_unbalanced_parens(self):
        querystr = SLQuery("(character:caliborn OR character:calliope (homestuck))")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            [['character:caliborn', 'character:calliope (homestuck)']]
        )

    def test_parse_sl_split_or(self):
        querystr = SLQuery("tag1 AND (tag2 OR tag3)")
        self.assertEqual(
            querylang.parse_sl_query(querystr),
            ['tag1', ['tag2', 'tag3']]
        )

    def test_parse_ml_split_or(self):
        querystr = MLQuery("tag1\ntag2 OR tag3")
        self.assertEqual(
            querylang.parse_ml_query(querystr),
            ['tag1', ['tag2', 'tag3']]
        )
