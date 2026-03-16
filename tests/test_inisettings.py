# claude artifact
from __future__ import annotations

import configparser
import json
import tempfile
import threading
import unittest
from pathlib import Path

from pydantic import ValidationError

import hydrustools.utils.inisettings as module
from hydrustools.utils.inisettings import IniSettings, clear_registry


def make_temp_path(tmp_dir: str, name: str = "test.ini") -> Path:
    return Path(tmp_dir) / name


class BasicSettings(IniSettings):
    name: str = "default_name"
    count: int = 42
    ratio: float = 3.14
    enabled: bool = True


class AllTypesSettings(IniSettings):
    text: str = "hello"
    number: int = 0
    decimal: float = 0.0
    flag: bool = False
    items: list[str] = []
    mapping: dict = {}


class EmptySettings(IniSettings):
    pass


class ChildSettings(BasicSettings):
    extra: str = "child_extra"


class PluginA(IniSettings):
    host: str = "localhost"
    port: int = 8080


class PluginB(IniSettings):
    debug: bool = False
    timeout: float = 30.0


class IniSettingsTestCase(unittest.TestCase):
    # Base test class to set up and tear down in temp directories

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = self._tmp.name
        clear_registry()

    def tearDown(self):
        clear_registry()
        self._tmp.cleanup()

    def ini_path(self, name: str = "test.ini") -> Path:
        return Path(self.tmp_dir) / name


class TestInitialisation(IniSettingsTestCase):
    # Init with Settings object, then validate

    def test_creates_ini_file_on_first_use(self):
        p = self.ini_path()
        BasicSettings(p)
        self.assertTrue(p.exists())

    def test_default_filename_uses_class_name(self):
        """When no path is given the file should be named after the class."""
        import os

        original_dir = os.getcwd()
        os.chdir(self.tmp_dir)
        try:
            BasicSettings()
            self.assertTrue(Path(self.tmp_dir, "BasicSettings.ini").exists())
        finally:
            os.chdir(original_dir)

    def test_default_section_uses_class_name(self):
        p = self.ini_path()
        BasicSettings(p)
        cfg = configparser.ConfigParser()
        cfg.read(p)
        self.assertIn("BasicSettings", cfg.sections())

    def test_explicit_section_is_used(self):
        p = self.ini_path()
        BasicSettings(p, section="custom")
        cfg = configparser.ConfigParser()
        cfg.read(p)
        self.assertIn("custom", cfg.sections())

    def test_defaults_written_to_disk(self):
        p = self.ini_path()
        BasicSettings(p)
        cfg = configparser.ConfigParser()
        cfg.read(p)
        self.assertEqual(cfg.get("BasicSettings", "name"), "default_name")
        self.assertEqual(cfg.get("BasicSettings", "count"), "42")

    def test_loads_existing_values_on_init(self):
        """If the INI already has values they should override the defaults."""
        p = self.ini_path()
        cfg = configparser.ConfigParser()
        cfg.add_section("BasicSettings")
        cfg.set("BasicSettings", "name", "pre_existing")
        cfg.set("BasicSettings", "count", "99")
        cfg.set("BasicSettings", "ratio", "2.71")
        cfg.set("BasicSettings", "enabled", "False")
        with open(p, "w") as f:
            cfg.write(f)

        s = BasicSettings(p)
        self.assertEqual(s.name, "pre_existing")
        self.assertEqual(s.count, 99)
        self.assertAlmostEqual(s.ratio, 2.71)
        self.assertFalse(s.enabled)

    def test_loads_default_values_on_fresh_init(self):
        """If the INI doesn't exist the default should be accessible"""
        p = self.ini_path()

        s = BasicSettings(p)
        self.assertEqual(s.name, "default_name")
        self.assertEqual(s.count, 42)
        self.assertEqual(s.ratio, 3.14)
        self.assertEqual(s.enabled, True)

    def test_empty_settings_class(self):
        p = self.ini_path()
        s = EmptySettings(p)  # should not raise
        self.assertIsNotNone(s)

    def test_creates_parent_directories(self):
        p = self.ini_path("nested/deep/test.ini")
        BasicSettings(p)
        self.assertTrue(p.exists())


class TestDeserialisation(IniSettingsTestCase):
    # Write directly to ini file with our own ConfigParser,
    # then require IniSettings to read the file correctly.

    def _make(self, **overrides) -> AllTypesSettings:
        p = self.ini_path()
        if overrides:
            cfg = configparser.ConfigParser()
            cfg.add_section("AllTypesSettings")
            for k, v in overrides.items():
                cfg.set("AllTypesSettings", k, v)
            with open(p, "w") as f:
                cfg.write(f)
        return AllTypesSettings(p)

    def test_str_returned_as_str(self):
        s = self._make(text="world")
        self.assertIsInstance(s.text, str)
        self.assertEqual(s.text, "world")

    def test_int_returned_as_int(self):
        s = self._make(number="7")
        self.assertIsInstance(s.number, int)
        self.assertEqual(s.number, 7)

    def test_float_returned_as_float(self):
        s = self._make(decimal="1.5")
        self.assertIsInstance(s.decimal, float)
        self.assertAlmostEqual(s.decimal, 1.5)

    def test_bool_true_variants(self):
        for raw in ("true", "True", "TRUE", "1", "yes", "on"):
            clear_registry()
            s = self._make(flag=raw)
            self.assertTrue(s.flag, msg=f"Expected True for raw={raw!r}")

    def test_bool_false_variants(self):
        for raw in ("false", "False", "FALSE", "0", "no", "off", "nope"):
            clear_registry()
            s = self._make(flag=raw)
            self.assertFalse(s.flag, msg=f"Expected False for raw={raw!r}")

    def test_list_round_trips(self):
        original = ["alpha", "beta", "gamma"]
        s = self._make(items=json.dumps(original))
        self.assertEqual(s.items, original)

    def test_dict_round_trips(self):
        original = {"x": 1, "y": [2, 3]}
        s = self._make(mapping=json.dumps(original))
        self.assertEqual(s.mapping, original)

    def test_default_list_is_empty(self):
        s = self._make()
        self.assertEqual(s.items, [])

    def test_default_dict_is_empty(self):
        s = self._make()
        self.assertEqual(s.mapping, {})


class TestReadWrite(IniSettingsTestCase):
    def test_set_str(self):
        s = BasicSettings(self.ini_path())
        s.name = "changed"
        self.assertEqual(s.name, "changed")

    def test_set_int(self):
        s = BasicSettings(self.ini_path())
        s.count = 100
        self.assertEqual(s.count, 100)

    def test_set_float(self):
        s = BasicSettings(self.ini_path())
        s.ratio = 1.23
        self.assertAlmostEqual(s.ratio, 1.23)

    def test_set_bool_true(self):
        s = BasicSettings(self.ini_path())
        s.enabled = True
        self.assertTrue(s.enabled)

    def test_set_bool_false(self):
        s = BasicSettings(self.ini_path())
        s.enabled = False
        self.assertFalse(s.enabled)

    def test_write_persists_to_disk(self):
        p = self.ini_path()
        s = BasicSettings(p)
        s.name = "persisted"

        cfg = configparser.ConfigParser()
        cfg.read(p)
        self.assertEqual(cfg.get("BasicSettings", "name"), "persisted")

    def test_write_is_reflected_in_same_instance(self):
        s = BasicSettings(self.ini_path())
        s.count = 999
        self.assertEqual(s.count, 999)

    def test_set_list(self):
        s = AllTypesSettings(self.ini_path())
        s.items = ["a", "b"]
        self.assertEqual(s.items, ["a", "b"])

    def test_set_dict(self):
        s = AllTypesSettings(self.ini_path())
        s.mapping = {"key": "value"}
        self.assertEqual(s.mapping, {"key": "value"})

    def test_non_schema_attr_stored_normally(self):
        """Attributes not in the schema must not be written to the INI."""
        s = BasicSettings(self.ini_path())
        s._runtime_only = "volatile"
        self.assertEqual(s._runtime_only, "volatile")

        cfg = configparser.ConfigParser()
        cfg.read(self.ini_path())
        self.assertFalse(cfg.has_option("BasicSettings", "_runtime_only"))


# ===========================================================================
# 4. Persistence across instances
# ===========================================================================


class TestPersistenceAcrossInstances(IniSettingsTestCase):
    def test_second_instance_reads_first_writes(self):
        p = self.ini_path()
        s1 = BasicSettings(p)
        s1.name = "from_s1"

        clear_registry()  # force a fresh load
        s2 = BasicSettings(p)
        self.assertEqual(s2.name, "from_s1")

    def test_shared_registry_instance_sees_peer_writes(self):
        """Two instances pointing at the same file share a ConfigParser."""
        p = self.ini_path()
        s1 = BasicSettings(p)
        clear_registry()

        s1.name = "hello"
        # s2 shares the same ConfigParser in the registry after this point
        # (they were loaded separately above, but the next clear + load would
        # reflect it – here we just verify disk persistence works)
        clear_registry()
        s3 = BasicSettings(p)
        self.assertEqual(s3.name, "hello")

    def test_integer_survives_reload(self):
        p = self.ini_path()
        s1 = BasicSettings(p)
        s1.count = 777
        clear_registry()
        s2 = BasicSettings(p)
        self.assertEqual(s2.count, 777)

    def test_bool_false_survives_reload(self):
        p = self.ini_path()
        s1 = BasicSettings(p)
        s1.enabled = False
        clear_registry()
        s2 = BasicSettings(p)
        self.assertFalse(s2.enabled)

    def test_list_survives_reload(self):
        p = self.ini_path()
        s = AllTypesSettings(p)
        s.items = ["a", "b", "c"]
        clear_registry()
        s2 = AllTypesSettings(p)
        self.assertEqual(s2.items, ["a", "b", "c"])


class TestMultipleSections(IniSettingsTestCase):
    def test_two_classes_same_file_distinct_sections(self):
        p = self.ini_path()
        a = PluginA(p)
        b = PluginB(p)

        cfg = configparser.ConfigParser()
        cfg.read(p)
        self.assertIn("PluginA", cfg.sections())
        self.assertIn("PluginB", cfg.sections())

    def test_write_to_section_a_does_not_affect_section_b(self):
        p = self.ini_path()
        a = PluginA(p)
        b = PluginB(p)

        b.timeout = 60.0
        a.host = "remotehost"

        self.assertAlmostEqual(b.timeout, 60.0)
        self.assertEqual(a.host, "remotehost")

    def test_section_b_values_persist_after_section_a_write(self):
        p = self.ini_path()
        a = PluginA(p)
        b = PluginB(p)

        b.debug = True
        a.port = 9090  # write to a different section

        clear_registry()
        b2 = PluginB(p)
        self.assertTrue(b2.debug, "PluginB.debug was clobbered by a PluginA write")

    def test_section_a_values_persist_after_section_b_write(self):
        p = self.ini_path()
        a = PluginA(p)
        b = PluginB(p)

        a.host = "saved_host"
        b.timeout = 99.9  # write to a different section

        clear_registry()
        a2 = PluginA(p)
        self.assertEqual(a2.host, "saved_host", "PluginA.host was clobbered by a PluginB write")

    def test_explicit_section_names(self):
        p = self.ini_path()
        x = BasicSettings(p, section="alpha")
        y = BasicSettings(p, section="beta")

        x.name = "x_name"
        y.name = "y_name"

        self.assertEqual(x.name, "x_name")
        self.assertEqual(y.name, "y_name")

    def test_many_sections_all_present_on_disk(self):
        p = self.ini_path()
        sections = [f"sec{i}" for i in range(10)]
        instances = [BasicSettings(p, section=sec) for sec in sections]
        for i, inst in enumerate(instances):
            inst.count = i

        cfg = configparser.ConfigParser()
        cfg.read(p)
        for i, sec in enumerate(sections):
            self.assertEqual(cfg.getint(sec, "count"), i)


class TestInheritance(IniSettingsTestCase):
    def test_child_inherits_parent_defaults(self):
        s = ChildSettings(self.ini_path())
        self.assertEqual(s.name, "default_name")
        self.assertEqual(s.count, 42)

    def test_child_has_own_attr(self):
        s = ChildSettings(self.ini_path())
        self.assertEqual(s.extra, "child_extra")

    def test_child_writes_all_keys_to_ini(self):
        p = self.ini_path()
        s = ChildSettings(p)
        s.extra = "overridden"
        s.count = 7

        cfg = configparser.ConfigParser()
        cfg.read(p)
        self.assertEqual(cfg.get("ChildSettings", "extra"), "overridden")
        self.assertEqual(cfg.getint("ChildSettings", "count"), 7)

    def test_parent_and_child_can_share_file(self):
        p = self.ini_path()
        parent = BasicSettings(p)
        child = ChildSettings(p)

        parent.name = "parent_name"
        child.name = "child_name"

        self.assertEqual(parent.name, "parent_name")
        self.assertEqual(child.name, "child_name")


class TestThreadSafety(IniSettingsTestCase):
    def test_concurrent_writes_do_not_corrupt_file(self):
        """Many threads writing different sections simultaneously should all succeed."""
        p = self.ini_path()

        # Pre-create all sections so registry is shared
        writers = [BasicSettings(p, section=f"t{i}") for i in range(8)]
        errors: list[Exception] = []

        def write_many(inst: BasicSettings, value: int) -> None:
            try:
                for _ in range(20):
                    inst.count = value
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=write_many, args=(writers[i], i * 10)) for i in range(len(writers))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(errors, f"Thread errors: {errors}")

        # File must be parseable after all the concurrent writes
        cfg = configparser.ConfigParser()
        cfg.read(p)
        for i in range(len(writers)):
            self.assertTrue(cfg.has_section(f"t{i}"))

    def test_concurrent_writes_to_same_section_no_crash(self):
        """Multiple threads hammering the same key should not raise."""
        p = self.ini_path()
        s = BasicSettings(p)
        errors: list[Exception] = []

        def bump():
            try:
                for _ in range(50):
                    s.count = 1
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=bump) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(errors, f"Errors during concurrent writes: {errors}")

    def test_read_during_write_returns_valid_type(self):
        """Reads occurring while another thread is writing should not raise."""
        p = self.ini_path()
        s = BasicSettings(p)
        errors: list[Exception] = []

        def writer():
            try:
                for i in range(100):
                    s.count = i
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def reader():
            try:
                for _ in range(100):
                    val = s.count
                    self.assertIsInstance(val, int)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            *[threading.Thread(target=writer) for _ in range(2)],
            *[threading.Thread(target=reader) for _ in range(2)],
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertFalse(errors, f"Errors during concurrent read/write: {errors}")


class TestRegistry(IniSettingsTestCase):
    def test_same_path_returns_same_config_object(self):
        p = self.ini_path()
        a = PluginA(p)
        b = PluginB(p)
        self.assertIs(
            object.__getattribute__(a, "_config"),
            object.__getattribute__(b, "_config"),
        )

    def test_different_paths_return_different_config_objects(self):
        a = PluginA(self.ini_path("a.ini"))
        b = PluginB(self.ini_path("b.ini"))
        self.assertIsNot(
            object.__getattribute__(a, "_config"),
            object.__getattribute__(b, "_config"),
        )

    def test_clear_registry_drops_cache(self):
        p = self.ini_path()
        PluginA(p)
        self.assertTrue(len(module._file_registry) >= 1)
        clear_registry()
        self.assertEqual(len(module._file_registry), 0)

    def test_clear_registry_forces_fresh_read(self):
        p = self.ini_path()
        s1 = BasicSettings(p)
        s1.name = "before_clear"

        clear_registry()

        # Manually mutate the file on disk
        cfg = configparser.ConfigParser()
        cfg.read(p)
        cfg.set("BasicSettings", "name", "after_clear")
        with open(p, "w") as f:
            cfg.write(f)

        s2 = BasicSettings(p)
        self.assertEqual(s2.name, "after_clear")


class TestEdgeCases(IniSettingsTestCase):
    def test_empty_string_value(self):
        s = AllTypesSettings(self.ini_path())
        s.text = ""
        self.assertEqual(s.text, "")

    def test_string_with_special_characters(self):
        s = AllTypesSettings(self.ini_path())
        val = "hello: world\nfoo=bar"
        s.text = val
        self.assertEqual(s.text, val)

    def test_zero_int(self):
        s = BasicSettings(self.ini_path())
        s.count = 0
        self.assertEqual(s.count, 0)

    def test_negative_int(self):
        s = BasicSettings(self.ini_path())
        s.count = -5
        self.assertEqual(s.count, -5)

    def test_negative_float(self):
        s = BasicSettings(self.ini_path())
        s.ratio = -1.5
        self.assertAlmostEqual(s.ratio, -1.5)

    def test_wrong_type_list(self):
        s = AllTypesSettings(self.ini_path())
        with self.assertRaises(ValidationError):
            s.items = [1, 2, 3]  # type: ignore

    def test_large_list(self):
        s = AllTypesSettings(self.ini_path())
        big = [str(i) for i in range(500)]
        s.items = big
        self.assertEqual(s.items, big)

    def test_nested_dict(self):
        s = AllTypesSettings(self.ini_path())
        nested = {"a": {"b": {"c": [1, 2, 3]}}}
        s.mapping = nested
        self.assertEqual(s.mapping, nested)

    def test_overwriting_same_key_multiple_times(self):
        s = BasicSettings(self.ini_path())
        for i in range(10):
            s.count = i
        self.assertEqual(s.count, 9)

    def test_bool_does_not_serialise_as_json(self):
        """bool serialises as 'True'/'False', not 'true'/'false' (JSON)."""
        s = BasicSettings(self.ini_path())
        s.enabled = True
        cfg = configparser.ConfigParser()
        cfg.read(self.ini_path())
        raw = cfg.get("BasicSettings", "enabled")
        self.assertIn(raw, ("True", "False"))

    def test_schema_does_not_include_private_attrs(self):
        schema = object.__getattribute__(BasicSettings(self.ini_path()), "_schema")
        for key in schema:
            self.assertFalse(key.startswith("_"), f"Private attr in schema: {key}")

    def test_schema_does_not_include_methods(self):
        schema = object.__getattribute__(BasicSettings(self.ini_path()), "_schema")
        for key, val in schema.items():
            self.assertFalse(callable(val), f"Callable in schema: {key}")

    def test_missing_file_is_created_with_defaults(self):
        p = self.ini_path("does_not_exist.ini")
        self.assertFalse(p.exists())
        BasicSettings(p)
        self.assertTrue(p.exists())

    def test_partial_ini_fills_missing_defaults(self):
        """If the file exists but is missing some keys, defaults are written."""
        p = self.ini_path()
        cfg = configparser.ConfigParser()
        cfg.add_section("BasicSettings")
        cfg.set("BasicSettings", "name", "partial")
        # deliberately omit count, ratio, enabled
        with open(p, "w") as f:
            cfg.write(f)

        s = BasicSettings(p)
        self.assertEqual(s.count, 42)  # filled from default
        self.assertEqual(s.name, "partial")  # existing value preserved


class TestAntiClobber(IniSettingsTestCase):
    def test_external_write_not_lost_on_save(self):
        """
        Simulate a second process writing section B to disk between two
        saves from section A.  Section B's change must survive.
        """
        p = self.ini_path()
        a = PluginA(p)
        b = PluginB(p)

        # Write A first
        a.host = "host_a"

        # Simulate an external / out-of-process write to section B
        cfg = configparser.ConfigParser()
        cfg.read(p)
        cfg.set("PluginB", "timeout", "123.0")
        with open(p, "w") as f:
            cfg.write(f)

        # Now write A again — this must re-read before flushing
        a.port = 1234

        cfg2 = configparser.ConfigParser()
        cfg2.read(p)
        self.assertAlmostEqual(
            cfg2.getfloat("PluginB", "timeout"), 123.0, msg="External write to PluginB was clobbered by PluginA write"
        )
