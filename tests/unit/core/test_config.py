import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, LogLevel, Settings


def _settings(**values: object) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_defaults_are_safe() -> None:
    settings = _settings()

    assert settings.cors_origins == []
    assert settings.api_key is None
    assert settings.auth_enabled is False
    assert settings.app_port == 8000


def test_values_are_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Calc")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "9000")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.local, http://b.local")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = _settings()

    assert settings.app_name == "Calc"
    assert settings.app_env is AppEnv.STAGING
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 9000
    assert settings.cors_origins == ["http://a.local", "http://b.local"]
    assert settings.log_level is LogLevel.DEBUG


def test_empty_cors_origins_means_disabled() -> None:
    assert _settings(cors_origins="").cors_origins == []
    assert _settings(cors_origins=" , ").cors_origins == []


def test_blank_api_key_keeps_authentication_disabled() -> None:
    assert _settings(api_key="   ").auth_enabled is False


def test_api_key_is_secret_and_enables_authentication() -> None:
    settings = _settings(api_key="s3cret")

    assert settings.auth_enabled is True
    assert "s3cret" not in repr(settings)


def test_wildcard_cors_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        _settings(app_env="production", cors_origins="*")


def test_wildcard_cors_is_allowed_outside_production() -> None:
    assert _settings(app_env="development", cors_origins="*").cors_origins == ["*"]


def test_invalid_port_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(app_port=70000)
