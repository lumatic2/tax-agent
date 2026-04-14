"""모델 레지스트리 로더."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REGISTRY_PATH = Path(__file__).parent / "registry.yaml"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    ollama_tag: str
    context: int
    temperature: float
    num_predict: int
    prompt_version: str
    notes: str
    bench: dict[str, Any]


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _to_spec(raw: dict[str, Any]) -> ModelSpec:
    return ModelSpec(
        name=raw["name"],
        ollama_tag=raw.get("ollama_tag", raw["name"]),
        context=int(raw.get("context", 8192)),
        temperature=float(raw.get("temperature", 0.0)),
        num_predict=int(raw.get("num_predict", 1024)),
        prompt_version=raw.get("prompt_version", "v3"),
        notes=raw.get("notes", ""),
        bench=raw.get("bench") or {},
    )


def list_models() -> list[ModelSpec]:
    return [_to_spec(m) for m in _load().get("models", [])]


def default_model() -> str:
    return _load().get("default") or list_models()[0].name


def get_spec(name: str | None = None) -> ModelSpec:
    target = name or default_model()
    for m in list_models():
        if m.name == target or m.ollama_tag == target:
            return m
    raise KeyError(
        f"unknown model '{target}'. registered: {[m.name for m in list_models()]}"
    )
