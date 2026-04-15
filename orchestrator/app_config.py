from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

CONFIG_PATH_ENV_VAR = "DMC_CONFIG_PATH"
_DEFAULT_CONFIG_PATH = Path(__file__).with_name("app_config.json")


@lru_cache(maxsize=1)
def _load_config() -> dict[str, Any]:
    config_path = Path(os.environ.get(CONFIG_PATH_ENV_VAR, _DEFAULT_CONFIG_PATH))
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Config root must be an object: {config_path}")

    return data


def _get_ollama_section() -> dict[str, Any]:
    ollama = _load_config().get("ollama", {})
    if not isinstance(ollama, dict):
        raise ValueError("Config key 'ollama' must be an object")
    return ollama


def _get_llm_section() -> dict[str, Any]:
    llm = _load_config().get("llm")
    if llm is None:
        # Backwards compatibility for older config files that only define `ollama`.
        return {
            "default_provider": "ollama",
            "providers": {
                "ollama": _get_ollama_section(),
            },
        }
    if not isinstance(llm, dict):
        raise ValueError("Config key 'llm' must be an object")
    return llm


def get_default_provider() -> str:
    default_provider = str(_get_llm_section().get("default_provider", "ollama")).strip().lower()
    if not default_provider:
        raise ValueError("Config key 'llm.default_provider' must be a non-empty string")
    return default_provider


def get_provider_names() -> list[str]:
    providers = _get_llm_section().get("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("Config key 'llm.providers' must be an object")
    names = [str(key).strip().lower() for key in providers.keys() if str(key).strip()]
    if not names:
        names = ["ollama"]
    if get_default_provider() not in names:
        names.insert(0, get_default_provider())
    return list(dict.fromkeys(names))


def _get_provider_section(provider: str) -> dict[str, Any]:
    requested = str(provider or "").strip().lower() or get_default_provider()
    providers = _get_llm_section().get("providers", {})
    if not isinstance(providers, dict):
        raise ValueError("Config key 'llm.providers' must be an object")
    payload = providers.get(requested)
    if payload is None:
        if requested == "ollama":
            return _get_ollama_section()
        raise ValueError(f"Unknown provider '{requested}'. Available providers: {', '.join(get_provider_names())}")
    if not isinstance(payload, dict):
        raise ValueError(f"Config key 'llm.providers.{requested}' must be an object")
    return payload


def get_ollama_default_model() -> str:
    model = _get_ollama_section().get("default_model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Config key 'ollama.default_model' must be a non-empty string")
    return model.strip()


def get_ollama_model_choices() -> list[str]:
    default_model = get_ollama_default_model()
    raw_choices = _get_ollama_section().get("model_choices")
    if raw_choices is None:
        return [default_model]
    if not isinstance(raw_choices, list):
        raise ValueError("Config key 'ollama.model_choices' must be an array of strings")

    choices: list[str] = []
    for item in raw_choices:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Config key 'ollama.model_choices' entries must be non-empty strings")
        normalized = item.strip()
        if normalized not in choices:
            choices.append(normalized)

    if not choices:
        raise ValueError("Config key 'ollama.model_choices' must contain at least one model string")
    if default_model not in choices:
        choices.insert(0, default_model)
    return choices


def get_ollama_default_options() -> dict[str, Any]:
    options = _get_ollama_section().get("default_options", {})
    if not isinstance(options, dict):
        raise ValueError("Config key 'ollama.default_options' must be an object")
    return copy.deepcopy(options)


def get_ollama_stage_options() -> dict[str, dict[str, Any]]:
    stage_options = _get_ollama_section().get("stage_options", {})
    if not isinstance(stage_options, dict):
        raise ValueError("Config key 'ollama.stage_options' must be an object")
    return copy.deepcopy(stage_options)


def get_roll_mode() -> str:
    rolls = _load_config().get("rolls", {})
    if not isinstance(rolls, dict):
        raise ValueError("Config key 'rolls' must be an object")
    mode = str(rolls.get("mode", "auto")).strip().lower()
    if mode not in {"auto", "manual"}:
        raise ValueError("Config key 'rolls.mode' must be 'auto' or 'manual'")
    return mode


def get_default_model(provider: str | None = None) -> str:
    provider_name = str(provider or get_default_provider()).strip().lower()
    if provider_name == "ollama" and "llm" not in _load_config():
        return get_ollama_default_model()
    payload = _get_provider_section(provider_name)
    model = payload.get("default_model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"Config key 'llm.providers.{provider_name}.default_model' must be a non-empty string")
    return model.strip()


def get_model_choices(provider: str | None = None) -> list[str]:
    provider_name = str(provider or get_default_provider()).strip().lower()
    if provider_name == "ollama" and "llm" not in _load_config():
        return get_ollama_model_choices()
    default_model = get_default_model(provider_name)
    raw_choices = _get_provider_section(provider_name).get("model_choices")
    if raw_choices is None:
        return [default_model]
    if not isinstance(raw_choices, list):
        raise ValueError(f"Config key 'llm.providers.{provider_name}.model_choices' must be an array of strings")

    choices: list[str] = []
    for item in raw_choices:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Config key 'llm.providers.{provider_name}.model_choices' entries must be non-empty strings")
        normalized = item.strip()
        if normalized not in choices:
            choices.append(normalized)

    if default_model not in choices:
        choices.insert(0, default_model)
    return choices


def get_provider_default_options(provider: str | None = None) -> dict[str, Any]:
    provider_name = str(provider or get_default_provider()).strip().lower()
    if provider_name == "ollama" and "llm" not in _load_config():
        return get_ollama_default_options()
    options = _get_provider_section(provider_name).get("default_options", {})
    if not isinstance(options, dict):
        raise ValueError(f"Config key 'llm.providers.{provider_name}.default_options' must be an object")
    return copy.deepcopy(options)


def get_provider_stage_options(provider: str | None = None) -> dict[str, dict[str, Any]]:
    provider_name = str(provider or get_default_provider()).strip().lower()
    if provider_name == "ollama" and "llm" not in _load_config():
        return get_ollama_stage_options()
    stage_options = _get_provider_section(provider_name).get("stage_options", {})
    if not isinstance(stage_options, dict):
        raise ValueError(f"Config key 'llm.providers.{provider_name}.stage_options' must be an object")
    return copy.deepcopy(stage_options)
