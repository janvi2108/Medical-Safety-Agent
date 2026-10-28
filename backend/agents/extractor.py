"""
agents/extractor.py
AGENT 1 - Medication Extractor

Reads a raw clinical note and produces a structured, validated list of
medications. The only agent that reads free text directly - everything
downstream works with clean structured data.

Does NOT determine whether medications interact - explicitly out of scope,
handled by Agent 2 using a real database instead of LLM reasoning.
"""

from pathlib import Path
from backend.services.llm.llm_client import (
    LLMConfigurationError,
    LLMProviderError,
    get_llm_client,
)
from backend.api.schemas import ExtractionResult, Medication

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extractor.txt"


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_medications(clinical_note: str) -> ExtractionResult:
    if not clinical_note or not clinical_note.strip():
        raise ValueError("clinical_note must not be empty")

    llm = get_llm_client()
    system_prompt = _load_prompt()

    user_prompt = f"""Extract all medications mentioned in this clinical note.

CLINICAL NOTE:
\"\"\"
{clinical_note}
\"\"\"

Return ONLY a JSON object matching this exact structure:
{{
  "medications": [
    {{"name": "<name as written>", "dose": "<dose or null>", "frequency": "<frequency or null>", "route": "<route or null>"}}
  ]
}}
If no medications are found, return {{"medications": []}}.
"""

    try:
        raw = llm.get_json_completion(system_prompt, user_prompt)
    except (LLMConfigurationError, LLMProviderError):
        raise
    except Exception as e:
        raise LLMProviderError("Medication extraction could not be completed. Check provider configuration and status.") from e

    try:
        if not isinstance(raw, dict) or not isinstance(raw.get("medications"), list):
            raise TypeError("expected an object with a medications list")
        medications = [Medication(**m) for m in raw["medications"]]
    except Exception as e:
        raise RuntimeError("Medication extraction returned malformed structured data.") from e

    return ExtractionResult(medications=medications)
