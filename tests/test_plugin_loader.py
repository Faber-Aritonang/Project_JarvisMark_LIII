"""Tests for core/plugin_loader.py — plugin discovery and dispatch."""

import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.plugin_loader import (
    PluginRecord,
    PluginRegistry,
    _call_run,
    _validate,
    discover_plugins,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_plugin(path: Path, code: str) -> None:
    """Write a .py plugin file to *path* with the given source."""
    path.write_text(textwrap.dedent(code), encoding="utf-8")


def _dummy_run(parameters, **kwargs):
    return f"ran with {parameters}"


# ── _validate ─────────────────────────────────────────────────────────────────


class TestValidate:
    def _module_with(self, **attrs):
        """Create a fake module-like object."""
        m = type("M", (), attrs)()
        return m

    def test_valid_plugin(self):
        m = self._module_with(
            PLUGIN={"name": "myplug", "description": "does stuff", "parameters": {"type": "OBJECT", "properties": {}}},
            run=_dummy_run,
        )
        rec = _validate(m, "myplug.py")
        assert rec.valid
        assert rec.name == "myplug"
        assert rec.description == "does stuff"

    def test_missing_plugin_dict(self):
        m = self._module_with()
        rec = _validate(m, "bad.py")
        assert not rec.valid
        assert "Missing PLUGIN" in rec.error

    def test_bad_name(self):
        m = self._module_with(PLUGIN={"name": "123bad", "description": "x"})
        rec = _validate(m, "bad.py")
        assert not rec.valid
        assert "name" in rec.error.lower()

    def test_missing_description(self):
        m = self._module_with(PLUGIN={"name": "ok", "description": ""})
        rec = _validate(m, "ok.py")
        assert not rec.valid
        assert "description" in rec.error.lower()

    def test_missing_run(self):
        m = self._module_with(PLUGIN={"name": "ok", "description": "x"})
        rec = _validate(m, "ok.py")
        assert not rec.valid
        assert "run" in rec.error.lower()

    def test_bad_parameters_type(self):
        m = self._module_with(
            PLUGIN={"name": "ok", "description": "x", "parameters": "bad"},
            run=_dummy_run,
        )
        rec = _validate(m, "ok.py")
        assert not rec.valid
        assert "parameters" in rec.error.lower()

    def test_with_settings(self):
        m = self._module_with(
            PLUGIN={"name": "ok", "description": "x"},
            PLUGIN_SETTINGS={"namespace": "ok_ns", "title": "OK Settings", "fields": []},
            run=_dummy_run,
        )
        rec = _validate(m, "ok.py")
        assert rec.valid
        assert rec.settings is not None
        assert rec.settings["namespace"] == "ok_ns"

    def test_bad_settings_ignored(self):
        m = self._module_with(
            PLUGIN={"name": "ok", "description": "x"},
            PLUGIN_SETTINGS="not a dict",
            run=_dummy_run,
        )
        rec = _validate(m, "ok.py")
        assert rec.valid
        assert rec.settings is None


# ── _call_run ─────────────────────────────────────────────────────────────────


class TestCallRun:
    def test_basic(self):
        def fn(parameters):
            return f"p={parameters}"
        assert _call_run(fn, {"a": 1}, None, None) == "p={'a': 1}"

    def test_with_player_kwarg(self):
        def fn(parameters, player=None):
            return f"player={player}"
        result = _call_run(fn, {}, "myplayer", None)
        assert result == "player=myplayer"

    def test_with_kwargs_catchall(self):
        def fn(parameters, **kwargs):
            return f"got {len(kwargs)} kwargs"
        result = _call_run(fn, {}, "p", "m")
        assert "2" in result

    def test_no_player_if_not_declared(self):
        def fn(parameters):
            return "ok"
        assert _call_run(fn, {}, "p", "m") == "ok"


# ── PluginRegistry ────────────────────────────────────────────────────────────


class TestPluginRegistry:
    def _make_registry(self, plugins=None, all_records=None):
        log = MagicMock()
        reg = PluginRegistry(plugins or {}, log)
        reg._all_records = all_records or []
        return reg

    @patch("core.plugin_loader.get_plugin_enabled", return_value=True)
    def test_has(self, _):
        rec = PluginRecord(name="foo", valid=True, run=_dummy_run)
        reg = self._make_registry({"foo": rec})
        assert reg.has("foo")
        assert not reg.has("bar")

    @patch("core.plugin_loader.get_plugin_enabled", return_value=True)
    def test_get_tool_declarations(self, _):
        rec = PluginRecord(name="foo", description="x", parameters={"type": "OBJECT", "properties": {}}, valid=True)
        reg = self._make_registry({"foo": rec})
        decls = reg.get_tool_declarations()
        assert len(decls) == 1
        assert decls[0]["name"] == "foo"

    @patch("core.plugin_loader.get_plugin_enabled", return_value=False)
    def test_disabled_plugin_hidden_from_declarations(self, _):
        rec = PluginRecord(name="foo", description="x", valid=True)
        reg = self._make_registry({"foo": rec})
        assert reg.get_tool_declarations() == []

    @patch("core.plugin_loader.get_plugin_enabled", return_value=True)
    def test_run_existing(self, _):
        rec = PluginRecord(name="foo", valid=True, run=lambda p, **kw: "ok")
        reg = self._make_registry({"foo": rec})
        assert reg.run("foo", {}) == "ok"

    @patch("core.plugin_loader.get_plugin_enabled", return_value=True)
    def test_run_missing(self, _):
        reg = self._make_registry()
        assert "not available" in reg.run("nope", {})

    @patch("core.plugin_loader.get_plugin_enabled", return_value=True)
    def test_run_crashing(self, _):
        def boom(p, **kw):
            raise RuntimeError("crash")
        rec = PluginRecord(name="foo", valid=True, run=boom)
        reg = self._make_registry({"foo": rec})
        assert "failed" in reg.run("foo", {})

    @patch("core.plugin_loader.get_plugin_enabled", return_value=False)
    def test_run_disabled(self, _):
        rec = PluginRecord(name="foo", valid=True, run=lambda p, **kw: "ok")
        reg = self._make_registry({"foo": rec})
        assert "disabled" in reg.run("foo", {})

    @patch("core.plugin_loader.get_plugin_enabled", return_value=True)
    def test_list_for_ui(self, _):
        rec = PluginRecord(name="foo", description="x", file="foo.py", valid=True)
        reg = self._make_registry({"foo": rec}, [rec])
        items = reg.list_for_ui()
        assert len(items) == 1
        assert items[0]["name"] == "foo"
        assert items[0]["enabled"] is True

    @patch("core.plugin_loader.get_plugin_config", return_value={"k": "v"})
    @patch("core.plugin_loader.get_plugin_enabled", return_value=True)
    def test_settings_schemas(self, _, __):
        rec = PluginRecord(
            name="foo", valid=True, run=_dummy_run,
            settings={"namespace": "foo_ns", "title": "Foo", "fields": [{"key": "k"}]},
        )
        reg = self._make_registry({"foo": rec})
        schemas = reg.settings_schemas()
        assert len(schemas) == 1
        assert schemas[0]["values"] == {"k": "v"}


# ── discover_plugins ──────────────────────────────────────────────────────────


class TestDiscoverPlugins:
    def test_discovers_valid(self, tmp_path):
        _make_plugin(tmp_path / "good.py", """
            PLUGIN = {"name": "good", "description": "a good plugin"}
            def run(parameters, **kwargs):
                return "ok"
        """)
        reg = discover_plugins(tmp_path, set(), logger=MagicMock())
        assert reg.has("good")

    def test_skips_underscore(self, tmp_path):
        _make_plugin(tmp_path / "_hidden.py", """
            PLUGIN = {"name": "hidden", "description": "nope"}
            def run(parameters, **kwargs):
                return "ok"
        """)
        reg = discover_plugins(tmp_path, set(), logger=MagicMock())
        assert not reg.has("hidden")

    def test_skips_no_plugin(self, tmp_path):
        _make_plugin(tmp_path / "bare.py", """
            def run(parameters, **kwargs):
                return "ok"
        """)
        reg = discover_plugins(tmp_path, set(), logger=MagicMock())
        assert not reg.has("bare")

    def test_collision_with_core(self, tmp_path):
        _make_plugin(tmp_path / "web_search.py", """
            PLUGIN = {"name": "web_search", "description": "dup"}
            def run(parameters, **kwargs):
                return "ok"
        """)
        reg = discover_plugins(tmp_path, {"web_search"}, logger=MagicMock())
        assert not reg.has("web_search")

    def test_import_error(self, tmp_path):
        _make_plugin(tmp_path / "broken.py", """
            raise ImportError("no module named nonexistent_thing_xyz")
        """)
        reg = discover_plugins(tmp_path, set(), logger=MagicMock())
        assert len(reg.list_for_ui()) == 1
        assert not reg.list_for_ui()[0]["valid"]

    def test_empty_dir(self, tmp_path):
        reg = discover_plugins(tmp_path, set(), logger=MagicMock())
        assert len(reg.list_for_ui()) == 0

    def test_deterministic_order(self, tmp_path):
        for name in ["zeta.py", "alpha.py", "mu.py"]:
            _make_plugin(tmp_path / name, f"""
                PLUGIN = {{"name": "{name[:-3]}", "description": "x"}}
                def run(parameters, **kwargs):
                    return "ok"
            """)
        reg = discover_plugins(tmp_path, set(), logger=MagicMock())
        names = [r["name"] for r in reg.list_for_ui()]
        assert names == ["alpha", "mu", "zeta"]
