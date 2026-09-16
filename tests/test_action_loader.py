"""Tests for core/action_loader.py — action discovery and dispatch."""
from __future__ import annotations

import textwrap
from pathlib import Path

from core.action_loader import (
    ActionRecord,
    ActionRegistry,
    _validate,
    discover_actions,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_module(tmp_path: Path, name: str, tool_dict: str | None = None,
                 extra_code: str = "") -> Path:
    """Write a .py file in tmp_path and return its path."""
    code = ""
    if tool_dict:
        code += f"TOOL = {tool_dict}\n"
    code += extra_code
    path = tmp_path / f"{name}.py"
    path.write_text(code, encoding="utf-8")
    return path


def _dummy_handler(parameters=None, **kw):
    return "ok"


# ── _validate ────────────────────────────────────────────────────────────────

class TestValidate:
    """_validate takes a loaded module and returns an ActionRecord."""

    def test_valid_tool(self):
        """A well-formed TOOL dict produces a valid ActionRecord."""
        import types
        mod = types.SimpleNamespace(TOOL={
            "name": "test_action",
            "description": "Does something",
            "parameters": {"type": "OBJECT", "properties": {}},
            "handler": _dummy_handler,
        })
        rec = _validate(mod, "test_action.py")
        assert rec.valid
        assert rec.name == "test_action"
        assert rec.error == ""

    def test_missing_tool_dict(self):
        import types
        mod = types.SimpleNamespace()
        rec = _validate(mod, "helper.py")
        assert not rec.valid
        assert "No module-level TOOL dict" in rec.error

    def test_bad_name(self):
        import types
        mod = types.SimpleNamespace(TOOL={
            "name": "123-bad!",
            "description": "x",
            "parameters": {"type": "OBJECT", "properties": {}},
            "handler": _dummy_handler,
        })
        rec = _validate(mod, "bad.py")
        assert not rec.valid
        assert "name" in rec.error.lower()

    def test_missing_description(self):
        import types
        mod = types.SimpleNamespace(TOOL={
            "name": "test",
            "description": "",
            "parameters": {"type": "OBJECT", "properties": {}},
            "handler": _dummy_handler,
        })
        rec = _validate(mod, "test.py")
        assert not rec.valid
        assert "description" in rec.error.lower()

    def test_missing_handler(self):
        import types
        mod = types.SimpleNamespace(TOOL={
            "name": "test",
            "description": "Does something",
            "parameters": {"type": "OBJECT", "properties": {}},
        })
        rec = _validate(mod, "test.py")
        assert not rec.valid
        assert "handler" in rec.error.lower()

    def test_bad_parameters_type(self):
        import types
        mod = types.SimpleNamespace(TOOL={
            "name": "test",
            "description": "x",
            "parameters": {"type": "STRING"},
            "handler": _dummy_handler,
        })
        rec = _validate(mod, "test.py")
        assert not rec.valid
        assert "parameters" in rec.error.lower()


# ── ActionRegistry ───────────────────────────────────────────────────────────

class TestActionRegistry:
    def _make_registry(self, actions: dict[str, ActionRecord] | None = None):
        return ActionRegistry(actions or {}, logger=lambda m: None)

    def test_has(self):
        rec = ActionRecord(name="test", valid=True, handler=_dummy_handler)
        reg = self._make_registry({"test": rec})
        assert reg.has("test")
        assert not reg.has("other")

    def test_names(self):
        rec1 = ActionRecord(name="a", valid=True)
        rec2 = ActionRecord(name="b", valid=True)
        reg = self._make_registry({"a": rec1, "b": rec2})
        assert reg.names() == {"a", "b"}

    def test_get_tool_declarations(self):
        rec = ActionRecord(
            name="test", description="A test", valid=True,
            parameters={"type": "OBJECT", "properties": {"x": {"type": "STRING"}}},
        )
        reg = self._make_registry({"test": rec})
        decls = reg.get_tool_declarations()
        assert len(decls) == 1
        assert decls[0]["name"] == "test"
        assert decls[0]["description"] == "A test"

    def test_run_existing(self):
        rec = ActionRecord(name="test", valid=True, handler=_dummy_handler)
        reg = self._make_registry({"test": rec})
        result = reg.run("test", {})
        assert result == "ok"

    def test_run_missing(self):
        reg = self._make_registry()
        result = reg.run("nonexistent", {})
        assert "not available" in result.lower()

    def test_run_crashing_handler(self):
        def bad(parameters=None, **kw):
            raise RuntimeError("boom")

        rec = ActionRecord(name="crash", valid=True, handler=bad)
        reg = self._make_registry({"crash": rec})
        result = reg.run("crash", {})
        assert "failed" in result.lower()
        assert "boom" in result


# ── discover_actions ─────────────────────────────────────────────────────────

class TestDiscoverActions:
    def test_discovers_valid_action(self, tmp_path):
        code = textwrap.dedent("""\
            from core.action_loader import ActionRecord
            def _handler(parameters=None, **kw):
                return "ok"
            TOOL = {
                "name": "my_action",
                "description": "Test action",
                "parameters": {"type": "OBJECT", "properties": {}},
                "handler": _handler,
            }
        """)
        (tmp_path / "my_action.py").write_text(code, encoding="utf-8")
        reg = discover_actions(tmp_path)
        assert reg.has("my_action")

    def test_skips_underscore_files(self, tmp_path):
        _make_module(tmp_path, "_helper", extra_code="X = 1\n")
        reg = discover_actions(tmp_path)
        assert len(reg.names()) == 0

    def test_skips_files_without_tool(self, tmp_path):
        _make_module(tmp_path, "helper", extra_code="X = 1\n")
        reg = discover_actions(tmp_path)
        assert len(reg.names()) == 0

    def test_respects_reserved_names(self, tmp_path):
        _make_module(tmp_path, "reserved_act", tool_dict=str({
            "name": "system_status",
            "description": "Clashes with core",
            "parameters": {"type": "OBJECT", "properties": {}},
            "handler": _dummy_handler,
        }))
        reg = discover_actions(tmp_path, reserved_names={"system_status"})
        assert not reg.has("system_status")

    def test_handles_import_error(self, tmp_path):
        bad = tmp_path / "broken.py"
        bad.write_text("import nonexistent_module_xyz\n", encoding="utf-8")
        # Should not raise — just logs and skips
        reg = discover_actions(tmp_path)
        assert len(reg.names()) == 0

    def test_empty_directory(self, tmp_path):
        reg = discover_actions(tmp_path)
        assert len(reg.names()) == 0
