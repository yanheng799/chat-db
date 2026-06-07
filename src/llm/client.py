"""LLM client wrapper — thin abstraction over LangChain ChatOpenAI.

Provides a :func:`create_llm_caller` factory that returns an async callable
conforming to the :class:`~learning.l2_inference.LLMCaller` protocol.
"""

from __future__ import annotations

from typing import Any

from config.settings import Settings


def create_llm_caller(settings: Settings | None = None) -> Any:
    """Create an async LLM caller function.

    Returns a callable with signature
    ``async (system_prompt: str, user_prompt: str) -> str``
    that can be passed directly to :func:`~learning.l2_inference.call_llm_with_retry`.
    """
    if settings is None:
        settings = Settings()

    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        api_key=settings.dashscope_api_key,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout,
    )

    async def _caller(system_prompt: str, user_prompt: str) -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await llm.ainvoke(messages)
        return response.content

    return _caller
