"""Tests for core/llm_client.py — config loading and provider detection."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core import llm_client


class TestGetBaseDir:
    def test_normal_mode(self):
        """In normal mode, BASE_DIR is the project root (parent of core/)."""
        result = llm_client.get_base_dir()
        assert result.name != "core"
        assert (result / "core").is_dir() or result.name == "Mark-LIII-original"

    def test_frozen_mode(self, tmp_path, monkeypatch):
        """In frozen mode, BASE_DIR is the directory of the executable."""
        exe = tmp_path / "Dodol"
        exe.touch()
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys.executable", str(exe))
        try:
            result = llm_client.get_base_dir()
            assert result == tmp_path
        finally:
            monkeypatch.delattr("sys", "frozen", raising=False)


class TestLoadConfig:
    def test_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(llm_client, "CONFIG_PATH", tmp_path / "missing.json")
        result = llm_client._load_config()
        assert result == {}

    def test_valid_file(self, tmp_path, monkeypatch):
        config = tmp_path / "api_keys.json"
        config.write_text(json.dumps({"llm_provider": "openai"}))
        monkeypatch.setattr(llm_client, "CONFIG_PATH", config)
        result = llm_client._load_config()
        assert result["llm_provider"] == "openai"

    def test_corrupt_file(self, tmp_path, monkeypatch):
        config = tmp_path / "api_keys.json"
        config.write_text("{invalid json", encoding="utf-8")
        monkeypatch.setattr(llm_client, "CONFIG_PATH", config)
        result = llm_client._load_config()
        assert result == {}


class TestGetLlmProvider:
    def test_default_ollama(self, tmp_path, monkeypatch):
        monkeypatch.setattr(llm_client, "CONFIG_PATH", tmp_path / "missing.json")
        assert llm_client.get_llm_provider() == "ollama"

    def test_explicit_openai(self, tmp_path, monkeypatch):
        config = tmp_path / "api_keys.json"
        config.write_text(json.dumps({"llm_provider": "openai"}))
        monkeypatch.setattr(llm_client, "CONFIG_PATH", config)
        assert llm_client.get_llm_provider() == "openai"

    def test_lmstudio_alias(self, tmp_path, monkeypatch):
        config = tmp_path / "api_keys.json"
        config.write_text(json.dumps({"llm_provider": "lmstudio"}))
        monkeypatch.setattr(llm_client, "CONFIG_PATH", config)
        assert llm_client.get_llm_provider() == "openai"

    def test_localai_alias(self, tmp_path, monkeypatch):
        config = tmp_path / "api_keys.json"
        config.write_text(json.dumps({"llm_provider": "localai"}))
        monkeypatch.setattr(llm_client, "CONFIG_PATH", config)
        assert llm_client.get_llm_provider() == "openai"

    def test_unknown_defaults_ollama(self, tmp_path, monkeypatch):
        config = tmp_path / "api_keys.json"
        config.write_text(json.dumps({"llm_provider": "something_else"}))
        monkeypatch.setattr(llm_client, "CONFIG_PATH", config)
        assert llm_client.get_llm_provider() == "ollama"


class TestGetLlmSettings:
    def test_defaults(self, tmp_path, monkeypatch):
        monkeypatch.setattr(llm_client, "CONFIG_PATH", tmp_path / "missing.json")
        url, model = llm_client.get_llm_settings()
        assert url == "http://localhost:11434"
        assert model == "llama3.2"

    def test_custom(self, tmp_path, monkeypatch):
        config = tmp_path / "api_keys.json"
        config.write_text(json.dumps({
            "llm_url": "http://localhost:1234",
            "llm_model": "mistral",
        }))
        monkeypatch.setattr(llm_client, "CONFIG_PATH", config)
        url, model = llm_client.get_llm_settings()
        assert url == "http://localhost:1234"
        assert model == "mistral"
