from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import APITimeoutError, AuthenticationError

from backend.config import config
from backend.services.llm.llm_client import (
    LLMConfigurationError,
    LLMProviderError,
    OpenAICompatibleProvider,
    get_llm_client,
)


def _provider(create):
    provider = object.__new__(OpenAICompatibleProvider)
    provider.model = "test-model"
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )
    return provider


def test_json_completion_parses_mocked_provider_response():
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"medications": []}'))])
    provider = _provider(Mock(return_value=response))

    assert provider.get_json_completion("system", "user") == {"medications": []}


def test_invalid_json_from_provider_is_reported_without_echoing_content():
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="private model output"))])
    provider = _provider(Mock(return_value=response))

    with pytest.raises(LLMProviderError, match="invalid JSON") as exc_info:
        provider.get_json_completion("system", "user")
    assert "private model output" not in str(exc_info.value)


def test_provider_timeout_is_actionable_and_does_not_escape_raw_sdk_error():
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    provider = _provider(Mock(side_effect=APITimeoutError(request=request)))

    with pytest.raises(LLMProviderError, match="timed out") as exc_info:
        provider.get_text_completion("system", "user")
    assert "example.test" not in str(exc_info.value)


def test_provider_auth_error_does_not_echo_provider_body_or_credential(monkeypatch):
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(401, request=request)
    fake_private_value = "test-private-provider-value"
    sdk_error = AuthenticationError(
        fake_private_value,
        response=response,
        body={"message": fake_private_value},
    )
    provider = _provider(Mock(side_effect=sdk_error))

    with pytest.raises(LLMProviderError, match="authentication failed") as exc_info:
        provider.get_text_completion("system", "user")
    assert fake_private_value not in str(exc_info.value)


def test_invalid_provider_is_a_configuration_error_without_echoing_value(monkeypatch):
    private_mistyped_value = "not-a-supported-provider-private-value"
    monkeypatch.setattr(config, "LLM_PROVIDER", private_mistyped_value)

    with pytest.raises(LLMConfigurationError, match="Unsupported LLM_PROVIDER") as exc_info:
        get_llm_client()
    assert private_mistyped_value not in str(exc_info.value)


@pytest.mark.parametrize("field", ["LLM_BASE_URL", "LLM_MODEL"])
def test_empty_endpoint_or_model_is_actionable_configuration_error(monkeypatch, field):
    monkeypatch.setattr(config, "LLM_API_KEY", "test-dummy-key")
    monkeypatch.setattr(config, field, "")

    with pytest.raises(LLMConfigurationError, match=f"{field} is empty"):
        OpenAICompatibleProvider()


def test_invalid_base_url_is_actionable(monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "test-dummy-key")
    monkeypatch.setattr(config, "LLM_BASE_URL", "not-a-url")

    with pytest.raises(LLMConfigurationError, match="absolute HTTP or HTTPS URL"):
        OpenAICompatibleProvider()
