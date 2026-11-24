"""Unit test pemilihan provider LLM dan system prompt."""

from datetime import datetime
from unittest.mock import Mock

import pytest

import main


def test_build_system_prompt_grounds_date_and_evidence_priority():
    prompt = main.build_system_prompt()

    assert f"Today's date is {datetime.now().strftime('%Y-%m-%d')}." in prompt
    assert "trust the tool results" in prompt
    assert "cite the source URLs" in prompt


def test_load_llm_selects_modelhub_when_api_key_is_set(monkeypatch):
    model = Mock()
    modelhub = Mock(return_value=model)
    azure = Mock()
    monkeypatch.setattr(main.config, "MODELHUB_API_KEY", "modelhub-key")
    monkeypatch.setattr(main.config, "MODELHUB_BASE_URL", "https://modelhub.example/v1")
    monkeypatch.setattr(main.config, "MODELHUB_MODEL_NAME", "example-model")
    monkeypatch.setattr(main, "ChatOpenAI", modelhub)
    monkeypatch.setattr(main, "AzureChatOpenAI", azure)

    result = main.load_llm()

    assert result is model
    modelhub.assert_called_once_with(
        api_key="modelhub-key",
        base_url="https://modelhub.example/v1",
        model="example-model",
        default_headers={"User-Agent": "curl/8.0"},
        temperature=0.7,
        max_tokens=1500,
        timeout=60,
        max_retries=2,
    )
    azure.assert_not_called()


def test_load_llm_rejects_incomplete_modelhub_config(monkeypatch):
    modelhub = Mock()
    monkeypatch.setattr(main.config, "MODELHUB_API_KEY", "modelhub-key")
    monkeypatch.setattr(main.config, "MODELHUB_BASE_URL", None)
    monkeypatch.setattr(main.config, "MODELHUB_MODEL_NAME", "example-model")
    monkeypatch.setattr(main, "ChatOpenAI", modelhub)

    with pytest.raises(ValueError, match="MODELHUB_BASE_URL dan MODELHUB_MODEL_NAME"):
        main.load_llm()

    modelhub.assert_not_called()


def test_load_llm_uses_azure_when_modelhub_key_is_absent(monkeypatch):
    model = Mock()
    azure = Mock(return_value=model)
    modelhub = Mock()
    monkeypatch.setattr(main.config, "MODELHUB_API_KEY", None)
    monkeypatch.setattr(main.config, "AZURE_OPENAI_ENDPOINT", "https://azure.example/")
    monkeypatch.setattr(main.config, "AZURE_OPENAI_API_KEY", "azure-key")
    monkeypatch.setattr(main.config, "AZURE_OPENAI_PREVIEW_API_VERSION", "2024-12-01-preview")
    monkeypatch.setattr(main, "AzureChatOpenAI", azure)
    monkeypatch.setattr(main, "ChatOpenAI", modelhub)

    result = main.load_llm()

    assert result is model
    azure.assert_called_once_with(
        api_key=main.config.AZURE_OPENAI_API_KEY,
        azure_endpoint=main.config.AZURE_OPENAI_ENDPOINT,
        azure_deployment=main.config.AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version=main.config.AZURE_OPENAI_PREVIEW_API_VERSION,
        temperature=0.7,
        max_tokens=1500,
        timeout=60,
        max_retries=2,
    )
    modelhub.assert_not_called()


def test_load_llm_rejects_incomplete_azure_config(monkeypatch):
    azure = Mock()
    monkeypatch.setattr(main.config, "MODELHUB_API_KEY", None)
    monkeypatch.setattr(main.config, "AZURE_OPENAI_ENDPOINT", None)
    monkeypatch.setattr(main.config, "AZURE_OPENAI_API_KEY", "azure-key")
    monkeypatch.setattr(main.config, "AZURE_OPENAI_PREVIEW_API_VERSION", "2024-12-01-preview")
    monkeypatch.setattr(main, "AzureChatOpenAI", azure)

    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        main.load_llm()

    azure.assert_not_called()


def test_load_llm_raises_when_no_provider_is_configured(monkeypatch):
    azure = Mock()
    modelhub = Mock()
    monkeypatch.setattr(main.config, "MODELHUB_API_KEY", None)
    monkeypatch.setattr(main.config, "AZURE_OPENAI_API_KEY", None)
    monkeypatch.setattr(main, "AzureChatOpenAI", azure)
    monkeypatch.setattr(main, "ChatOpenAI", modelhub)

    with pytest.raises(ValueError, match="MODELHUB_API_KEY"):
        main.load_llm()

    azure.assert_not_called()
    modelhub.assert_not_called()
