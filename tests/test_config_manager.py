"""Tests for memory/config_manager.py — configuration persistence."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import memory.config_manager as cm


@pytest.fixture
def config_dir(tmp_path):
    """Point config_manager at a temporary directory for isolation."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "api_keys.json"
    with patch.object(cm, "CONFIG_DIR", cfg_dir), \
         patch.object(cm, "CONFIG_FILE", cfg_file):
        yield cfg_dir, cfg_file


class TestConfigExists:
    def test_no_file(self, config_dir):
        _, cfg_file = config_dir
        assert not cm.config_exists()

    def test_file_present(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text('{}', encoding="utf-8")
        assert cm.config_exists()


class TestSaveLoadApiKeys:
    def test_save_and_load(self, config_dir):
        _, cfg_file = config_dir
        cm.save_api_keys("test-key-1234567890")
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert data["gemini_api_key"] == "test-key-1234567890"

    def test_load_preserves_existing(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text(json.dumps({"voice_name": "Puck"}), encoding="utf-8")
        cm.save_api_keys("new-key-1234567890")
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert data["voice_name"] == "Puck"
        assert data["gemini_api_key"] == "new-key-1234567890"

    def test_load_no_file(self, config_dir):
        assert cm.load_api_keys() == {}

    def test_load_corrupt_file(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text("not json!!!", encoding="utf-8")
        result = cm.load_api_keys()
        assert result == {}

    def test_get_gemini_key(self, config_dir):
        cm.save_api_keys("sk-test-123456789012")
        assert cm.get_gemini_key() == "sk-test-123456789012"

    def test_get_gemini_key_missing(self, config_dir):
        assert cm.get_gemini_key() is None

    def test_is_configured(self, config_dir):
        cm.save_api_keys("a-very-long-key-value-here")
        assert cm.is_configured()

    def test_not_configured_short_key(self, config_dir):
        cm.save_api_keys("short")
        assert not cm.is_configured()


class TestAssistantConfig:
    def test_default_name(self, config_dir):
        assert cm.get_assistant_name() == "Dodol"

    def test_custom_name(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text(json.dumps({"assistant_name": "Friday"}), encoding="utf-8")
        assert cm.get_assistant_name() == "Friday"

    def test_empty_name_falls_back(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text(json.dumps({"assistant_name": ""}), encoding="utf-8")
        assert cm.get_assistant_name() == "Dodol"

    def test_save_assistant_config(self, config_dir):
        _, cfg_file = config_dir
        cm.save_assistant_config("Friday", "Tony")
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert data["assistant_name"] == "Friday"
        assert data["user_name"] == "Tony"


class TestVoice:
    def test_default_voice(self, config_dir):
        assert cm.get_voice() == "Charon"

    def test_custom_voice(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text(json.dumps({"voice_name": "Puck"}), encoding="utf-8")
        assert cm.get_voice() == "Puck"

    def test_invalid_voice_falls_back(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text(json.dumps({"voice_name": "InvalidVoice"}), encoding="utf-8")
        assert cm.get_voice() == "Charon"

    def test_save_voice(self, config_dir):
        cm.save_voice("Kore")
        data = json.loads(config_dir[1].read_text(encoding="utf-8"))
        assert data["voice_name"] == "Kore"

    def test_save_invalid_voice_saves_default(self, config_dir):
        cm.save_voice("BadVoice")
        data = json.loads(config_dir[1].read_text(encoding="utf-8"))
        assert data["voice_name"] == "Charon"


class TestWakeWord:
    def test_default_disabled(self, config_dir):
        assert cm.get_wake_word_enabled() is False

    def test_enable(self, config_dir):
        cm.save_wake_word_enabled(True)
        assert cm.get_wake_word_enabled() is True

    def test_disable(self, config_dir):
        cm.save_wake_word_enabled(True)
        cm.save_wake_word_enabled(False)
        assert cm.get_wake_word_enabled() is False


class TestAudioDevices:
    def test_default_input(self, config_dir):
        assert cm.get_input_device() == ""

    def test_save_input(self, config_dir):
        cm.save_input_device("Blue Yeti")
        assert cm.get_input_device() == "Blue Yeti"

    def test_default_output(self, config_dir):
        assert cm.get_output_device() == ""

    def test_save_output(self, config_dir):
        cm.save_output_device("Speakers (USB)")
        assert cm.get_output_device() == "Speakers (USB)"


class TestPluginConfig:
    def test_empty_config(self, config_dir):
        assert cm.get_plugin_config("my_plugin") == {}

    def test_save_and_get(self, config_dir):
        cm.save_plugin_config("my_plugin", {"api_key": "abc123"})
        assert cm.get_plugin_config("my_plugin") == {"api_key": "abc123"}

    def test_merge_config(self, config_dir):
        cm.save_plugin_config("my_plugin", {"a": 1})
        cm.save_plugin_config("my_plugin", {"b": 2})
        cfg = cm.get_plugin_config("my_plugin")
        assert cfg == {"a": 1, "b": 2}

    def test_get_setting(self, config_dir):
        cm.save_plugin_config("ns", {"key": "val"})
        assert cm.get_plugin_setting("ns", "key") == "val"
        assert cm.get_plugin_setting("ns", "missing", "default") == "default"
