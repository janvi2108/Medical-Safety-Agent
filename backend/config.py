"""
config.py

Central place for all configuration - every other file reads config values
through this module, never directly via os.getenv(). This means there is
exactly one place that knows where a setting comes from (a local .env file
during development, or Azure App Service settings / Key Vault in production).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOTENV_PATH = (PROJECT_ROOT / ".env").resolve()
_PROCESS_KEY_DEFINED_BEFORE_DOTENV = "LLM_API_KEY" in os.environ
_PROCESS_KEY_NONEMPTY_BEFORE_DOTENV = bool(os.environ.get("LLM_API_KEY", "").strip())
load_dotenv(DOTENV_PATH, override=False)


def _project_path(value: str | None, default: Path) -> str:
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


class ConfigurationError(RuntimeError):
    """A safe, actionable application configuration error."""


class Config:
    # --- LLM provider (provider-independent - see services/llm/) ---
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai_compatible").strip().lower()
    LLM_API_KEY = (os.getenv("LLM_API_KEY") or "").strip() or None
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip()

    # Reserved for later - not used until Azure OpenAI quota is available
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

    # --- Database ---
    DATABASE_URL = os.getenv("DATABASE_URL")  # PostgreSQL connection string
    USE_SQLITE_FALLBACK = os.getenv("USE_SQLITE_FALLBACK", "true").lower() == "true"
    SQLITE_PATH = _project_path(
        os.getenv("SQLITE_PATH"), PROJECT_ROOT / "data" / "processed" / "ddinter" / "ddinter.db"
    )

    # --- DDInter data locations ---
    RAW_DDINTER_DIR = _project_path(os.getenv("RAW_DDINTER_DIR"), PROJECT_ROOT / "data" / "raw" / "ddinter")
    PROCESSED_DDINTER_DIR = _project_path(
        os.getenv("PROCESSED_DDINTER_DIR"), PROJECT_ROOT / "data" / "processed" / "ddinter"
    )

    # --- Azure Key Vault (production only) ---
    USE_KEY_VAULT = os.getenv("USE_KEY_VAULT", "false").lower() == "true"
    AZURE_KEY_VAULT_URL = os.getenv("AZURE_KEY_VAULT_URL")

    # --- Application Insights (production only) ---
    APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    # --- CORS ---
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    @classmethod
    def resolve_secret(cls, env_value: str | None, key_vault_secret_name: str) -> str | None:
        """Returns a secret from Key Vault if enabled, else the plain env value."""
        if cls.USE_KEY_VAULT:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=cls.AZURE_KEY_VAULT_URL, credential=credential)
            return client.get_secret(key_vault_secret_name).value
        return env_value

    def validate(self):
        """Fail fast at startup if required configuration is missing."""
        missing = []
        if not self.LLM_API_KEY:
            missing.append("LLM_API_KEY")
        if not self.DATABASE_URL and not self.USE_SQLITE_FALLBACK:
            missing.append("DATABASE_URL (or set USE_SQLITE_FALLBACK=true for local dev)")
        if missing:
            raise EnvironmentError(
                f"Missing required configuration: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill in the values."
            )


def _load_key_vault_secrets(settings: Config) -> None:
    """Resolve the existing Azure secret names only when Key Vault is enabled."""
    if not settings.USE_KEY_VAULT:
        return
    try:
        api_key = settings.resolve_secret(settings.LLM_API_KEY, "llm-api-key")
        database_url = settings.resolve_secret(settings.DATABASE_URL, "database-connection-string")
    except Exception:
        raise ConfigurationError(
            "Unable to load required settings from Azure Key Vault. Verify the vault URL, managed identity, "
            "permissions, and configured secret names."
        ) from None
    settings.LLM_API_KEY = (api_key or "").strip() or None
    settings.DATABASE_URL = database_url


config = Config()
if "*" in config.CORS_ORIGINS:
    raise ConfigurationError("CORS_ORIGINS must list explicit frontend origins; wildcard origins are not allowed.")
_load_key_vault_secrets(config)


def safe_config_diagnostics() -> dict[str, str | bool]:
    """Return configuration-source flags only; never return secret values."""
    if config.USE_KEY_VAULT and config.LLM_API_KEY:
        key_source = "azure_key_vault"
    elif _PROCESS_KEY_DEFINED_BEFORE_DOTENV:
        key_source = "process_environment" if _PROCESS_KEY_NONEMPTY_BEFORE_DOTENV else "empty_process_environment"
    elif bool((config.LLM_API_KEY or "").strip()):
        key_source = "repository_root_dotenv"
    else:
        key_source = "missing"

    client_receives_key = False
    if config.LLM_PROVIDER == "openai_compatible" and config.LLM_API_KEY:
        try:
            from backend.services.llm.llm_client import OpenAICompatibleProvider

            provider = OpenAICompatibleProvider()
            client_receives_key = provider.client.api_key == config.LLM_API_KEY
        except Exception:
            # Diagnostics must stay safe and useful even when SDK setup fails.
            client_receives_key = False

    return {
        "project_root": str(PROJECT_ROOT),
        "dotenv_path": str(DOTENV_PATH),
        "dotenv_exists": DOTENV_PATH.is_file(),
        "llm_api_key_present": bool((config.LLM_API_KEY or "").strip()),
        "llm_api_key_source": key_source,
        "llm_client_receives_same_key": client_receives_key,
    }


if __name__ == "__main__":
    for name, value in safe_config_diagnostics().items():
        print(f"{name}={value}")
