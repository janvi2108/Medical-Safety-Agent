import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend.config import _load_key_vault_secrets, config, safe_config_diagnostics
from backend.services.llm.llm_client import LLMConfigurationError, OpenAICompatibleProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_config_from(cwd: Path, extra_environment: dict[str, str] | None = None) -> str:
    environment = os.environ.copy()
    environment.pop("RAW_DDINTER_DIR", None)
    environment["PYTHONPATH"] = str(PROJECT_ROOT)
    if extra_environment:
        environment.update(extra_environment)
    result = subprocess.run(
        [sys.executable, "-c", "from backend.config import config; print(config.RAW_DDINTER_DIR)"],
        cwd=cwd,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_default_data_path_is_project_relative_not_cwd_relative(tmp_path):
    assert _load_config_from(tmp_path) == str(PROJECT_ROOT / "data" / "raw" / "ddinter")


def test_environment_override_takes_precedence_over_project_defaults(tmp_path):
    override = str(tmp_path / "custom-ddinter")
    assert _load_config_from(tmp_path, {"RAW_DDINTER_DIR": override}) == override


def test_relative_data_path_override_resolves_from_project_root(tmp_path):
    output = _load_config_from(tmp_path, {"RAW_DDINTER_DIR": "data/custom-source"})
    assert output == str(PROJECT_ROOT / "data" / "custom-source")


def _run_isolated_config(project_root: Path, cwd: Path, extra_environment: dict[str, str] | None = None) -> str:
    isolated_backend = project_root / "backend"
    isolated_backend.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROJECT_ROOT / "backend" / "config.py", isolated_backend / "config.py")
    (isolated_backend / "__init__.py").write_text("", encoding="utf-8")

    environment = os.environ.copy()
    for name in ("LLM_API_KEY", "LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL"):
        environment.pop(name, None)
    environment["PYTHONPATH"] = str(project_root)
    if extra_environment:
        environment.update(extra_environment)
    code = (
        "import os, sys; from pathlib import Path; from backend.config import config, PROJECT_ROOT; "
        "print(PROJECT_ROOT.resolve() == Path(sys.argv[1]).resolve(), "
        "bool((config.LLM_API_KEY or '').strip()), "
        "config.LLM_API_KEY == os.getenv('LLM_API_KEY'), "
        "config.LLM_PROVIDER, config.LLM_BASE_URL, config.LLM_MODEL)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(project_root)],
        cwd=cwd,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_root_dotenv_is_loaded_when_working_directory_differs(tmp_path):
    project_root = tmp_path / "isolated-project"
    cwd = tmp_path / "unrelated-working-directory"
    project_root.mkdir()
    cwd.mkdir()
    (project_root / ".env").write_text(
        "LLM_PROVIDER=openai_compatible\n"
        "LLM_API_KEY=test-dummy-from-dotenv\n"
        "LLM_BASE_URL=https://api.groq.com/openai/v1\n"
        "LLM_MODEL=llama-3.3-70b-versatile\n",
        encoding="utf-8",
    )

    output = _run_isolated_config(project_root, cwd)
    assert output == (
        "True True True openai_compatible https://api.groq.com/openai/v1 llama-3.3-70b-versatile"
    )


def test_process_environment_key_takes_precedence_over_dotenv(tmp_path):
    project_root = tmp_path / "priority-project"
    cwd = tmp_path / "outside"
    project_root.mkdir()
    cwd.mkdir()
    (project_root / ".env").write_text("LLM_API_KEY=test-dummy-from-dotenv\n", encoding="utf-8")

    output = _run_isolated_config(project_root, cwd, {"LLM_API_KEY": "test-dummy-from-process"})
    assert output.startswith("True True True ")


def test_empty_process_key_is_not_replaced_by_dotenv(tmp_path):
    project_root = tmp_path / "empty-process-project"
    cwd = tmp_path / "outside"
    project_root.mkdir()
    cwd.mkdir()
    (project_root / ".env").write_text("LLM_API_KEY=test-dummy-from-dotenv\n", encoding="utf-8")

    output = _run_isolated_config(project_root, cwd, {"LLM_API_KEY": ""})
    assert output.startswith("True False False ")


@pytest.mark.parametrize("empty_value", [None, "", "   "])
def test_missing_or_empty_key_has_actionable_error(monkeypatch, empty_value):
    monkeypatch.setattr(config, "LLM_API_KEY", empty_value)
    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY is missing"):
        OpenAICompatibleProvider()


def test_configured_key_reaches_llm_client_and_diagnostic_never_prints_it(monkeypatch, capsys):
    dummy_key = "test-dummy-key-never-print"
    monkeypatch.setattr(config, "LLM_API_KEY", dummy_key)
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai_compatible")

    diagnostic = safe_config_diagnostics()
    print(diagnostic)
    output = capsys.readouterr().out

    assert diagnostic["llm_api_key_present"] is True
    assert diagnostic["llm_client_receives_same_key"] is True
    assert dummy_key not in output


def test_config_validation_uses_resolved_instance_values(monkeypatch):
    dummy_key = "test-dummy-key-for-validation"
    monkeypatch.setattr(config, "LLM_API_KEY", None)
    monkeypatch.setattr(config, "USE_SQLITE_FALLBACK", True)
    with pytest.raises(EnvironmentError, match="LLM_API_KEY") as exc_info:
        config.validate()
    assert dummy_key not in str(exc_info.value)

    monkeypatch.setattr(config, "LLM_API_KEY", dummy_key)
    config.validate()


def test_key_vault_secrets_are_resolved_into_backend_settings_without_logging_values():
    from types import SimpleNamespace

    calls = []
    fake_settings = SimpleNamespace(
        USE_KEY_VAULT=True,
        LLM_API_KEY=None,
        DATABASE_URL=None,
        resolve_secret=lambda existing, name: calls.append((existing, name)) or f"test-value-{name}",
    )

    _load_key_vault_secrets(fake_settings)

    assert fake_settings.LLM_API_KEY == "test-value-llm-api-key"
    assert fake_settings.DATABASE_URL == "test-value-database-connection-string"
    assert [name for _, name in calls] == ["llm-api-key", "database-connection-string"]


def test_key_vault_failure_has_safe_actionable_message():
    from types import SimpleNamespace

    fake_settings = SimpleNamespace(
        USE_KEY_VAULT=True,
        LLM_API_KEY=None,
        DATABASE_URL=None,
        resolve_secret=lambda *_args: (_ for _ in ()).throw(RuntimeError("test-private-value")),
    )
    from backend.config import ConfigurationError

    with pytest.raises(ConfigurationError, match="Azure Key Vault") as exc_info:
        _load_key_vault_secrets(fake_settings)
    assert "test-private-value" not in str(exc_info.value)


def test_wildcard_cors_origin_is_rejected_in_isolated_project(tmp_path):
    project_root = tmp_path / "cors-project"
    cwd = tmp_path / "outside-cors-project"
    isolated_backend = project_root / "backend"
    isolated_backend.mkdir(parents=True)
    cwd.mkdir()
    shutil.copy2(PROJECT_ROOT / "backend" / "config.py", isolated_backend / "config.py")
    (isolated_backend / "__init__.py").write_text("", encoding="utf-8")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    environment["CORS_ORIGINS"] = "*"

    result = subprocess.run(
        [sys.executable, "-c", "from backend.config import config"],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "wildcard origins are not allowed" in result.stderr
