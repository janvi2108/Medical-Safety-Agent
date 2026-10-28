"""
services/llm/llm_client.py

Concrete LLMProvider implementations, plus get_llm_client() - the ONLY thing
agents should import from this module.

Active: OpenAICompatibleProvider, pointed at Groq by default (Groq mirrors
OpenAI's request/response shape, so one class covers OpenAI, Groq, and most
other hosted LLM APIs).

Reserved: AzureOpenAIProvider. Not wired up or usable yet - Azure OpenAI
deployment is currently blocked by a 0 TPM quota on free-trial subscriptions,
which is a billing/quota restriction, not a code problem. The class exists
so that switching to it later is: implement the two methods with the
azure-ai-openai SDK, set LLM_PROVIDER=azure_openai. No agent changes needed.
"""

import json
from urllib.parse import urlparse
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)
from backend.config import config
from backend.services.llm.base import LLMProvider


class LLMConfigurationError(RuntimeError):
    """Local LLM configuration is missing or invalid."""


class LLMProviderError(RuntimeError):
    """A safe, user-actionable provider failure without request or secret data."""


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self):
        if not (config.LLM_API_KEY or "").strip():
            raise LLMConfigurationError(
                "LLM_API_KEY is missing. Add a valid provider key to the repository-root .env "
                "or process environment, then restart the backend."
            )
        if not config.LLM_BASE_URL:
            raise LLMConfigurationError("LLM_BASE_URL is empty. Configure the OpenAI-compatible provider URL.")
        parsed_base_url = urlparse(config.LLM_BASE_URL)
        if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
            raise LLMConfigurationError("LLM_BASE_URL must be an absolute HTTP or HTTPS URL.")
        if not config.LLM_MODEL:
            raise LLMConfigurationError("LLM_MODEL is empty. Configure a model available from the provider.")
        self.client = OpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            timeout=30.0,
            max_retries=0,
        )
        self.model = config.LLM_MODEL

    def _completion(self, **kwargs):
        try:
            return self.client.chat.completions.create(model=self.model, **kwargs)
        except AuthenticationError as exc:
            raise LLMProviderError(
                "LLM provider authentication failed. Check LLM_API_KEY in the repository-root .env or deployment settings."
            ) from exc
        except NotFoundError as exc:
            raise LLMProviderError(
                f"Configured LLM model '{self.model}' was not found. Update LLM_MODEL to a model available from the provider."
            ) from exc
        except RateLimitError as exc:
            raise LLMProviderError("LLM provider rate limit reached. Retry later or review the provider quota.") from exc
        except APITimeoutError as exc:
            raise LLMProviderError("LLM provider request timed out. Retry the analysis.") from exc
        except APIConnectionError as exc:
            raise LLMProviderError("Could not connect to the LLM provider. Check network access and provider status.") from exc
        except BadRequestError as exc:
            raise LLMProviderError(
                "LLM provider rejected the request. Check that the configured model supports the requested response format."
            ) from exc
        except APIStatusError as exc:
            raise LLMProviderError(
                f"LLM provider request failed with HTTP {exc.status_code}. Check provider status and configuration."
            ) from exc

    def get_json_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
        response = self._completion(
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as e:
            raise LLMProviderError("LLM provider returned invalid JSON for medication extraction.") from e

    def get_text_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        response = self._completion(
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content


class AzureOpenAIProvider(LLMProvider):
    """Placeholder for future use once Azure OpenAI quota is available. Not implemented."""

    def __init__(self):
        raise LLMConfigurationError(
            "Azure OpenAI provider support is not implemented yet. Use LLM_PROVIDER=openai_compatible."
        )

    def get_json_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
        raise NotImplementedError

    def get_text_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        raise NotImplementedError


_PROVIDERS = {
    "openai_compatible": OpenAICompatibleProvider,
    "azure_openai": AzureOpenAIProvider,
}


def get_llm_client() -> LLMProvider:
    provider_class = _PROVIDERS.get(config.LLM_PROVIDER)
    if provider_class is None:
        raise LLMConfigurationError(
            "Unsupported LLM_PROVIDER. Use openai_compatible for the configured Groq-compatible endpoint."
        )
    return provider_class()
