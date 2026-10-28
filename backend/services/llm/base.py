"""
services/llm/base.py

Defines the LLM provider interface. Agents depend on THIS interface, never
on a concrete provider - that's what makes the architecture provider-
independent. Swapping providers means adding one class in llm_client.py and
changing a config value, with zero changes to any agent.
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def get_json_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
        """Call the model and return a parsed JSON dict. Used for structured extraction."""
        raise NotImplementedError

    @abstractmethod
    def get_text_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        """Call the model and return free-text output."""
        raise NotImplementedError
