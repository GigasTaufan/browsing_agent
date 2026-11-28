"""Unit test pemilihan provider LLM dan system prompt."""

from unittest.mock import Mock

import main


def test_load_llm_selects_modelhub_when_api_key_is_set(monkeypatch):
    model = Mock()
    modelhub = Mock(return_value=model)
    azure = Mock()
    monkeypatch.setattr(main.config, "MODELHUB_API_KEY", "modelhub-key")
    monkeypatch.setattr(main.config, "MODELHUB_BASE_URL", "https://modelhub.example/v1")
    monkeypatch.setattr(main.config, "MODELHUB_MODEL_NAME", "example-model")
    monkeypatch.setattr(main.config, "MODELHUB_USER_AGENT", "test-agent/1")
    monkeypatch.setattr(main, "ChatOpenAI", modelhub)
    monkeypatch.setattr(main, "AzureChatOpenAI", azure)

    result = main.load_llm()

    assert result is model
    modelhub.assert_called_once_with(
        api_key="modelhub-key",
        base_url="https://modelhub.example/v1",
        model="example-model",
        default_headers={"User-Agent": "test-agent/1"},
        temperature=0.7,
        max_tokens=1500,
        timeout=60,
        max_retries=2,
    )
    azure.assert_not_called()


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
