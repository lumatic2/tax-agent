"""LLM 어댑터·레지스트리.

tax-agent 내 모든 Ollama 호출은 `get_llm()` 팩토리를 경유한다.
모델 교체는 `registry.yaml` 수정만으로 끝난다.
"""
from agent.llm.adapter import get_llm
from agent.llm.registry import (
    ModelSpec,
    default_model,
    get_spec,
    list_models,
)

__all__ = ["get_llm", "ModelSpec", "default_model", "get_spec", "list_models"]
