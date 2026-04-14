"""Ollama 어댑터.

`get_llm(name)` 이 유일한 진입점. ChatOllama 인스턴스를 spec 기본값과 함께 반환한다.
오버라이드가 필요하면 kwargs 로 전달 (temperature/num_predict 등).
"""
from __future__ import annotations

from typing import Any

from agent.llm.registry import ModelSpec, get_spec


def get_llm(model: str | None = None, **overrides: Any):
    """LangChain ChatOllama 인스턴스를 레지스트리 spec 기준으로 생성.

    Args:
        model: 레지스트리 name 또는 ollama_tag. None → default.
        **overrides: temperature, num_predict 등 spec 기본값 덮어쓰기.
    """
    from langchain_ollama import ChatOllama

    spec: ModelSpec = get_spec(model)
    kwargs = dict(
        model=spec.ollama_tag,
        temperature=spec.temperature,
        num_predict=spec.num_predict,
    )
    kwargs.update(overrides)
    return ChatOllama(**kwargs)
