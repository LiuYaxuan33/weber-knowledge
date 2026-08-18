import pytest

import rag_service
from rag_service import RAGConfigurationError, format_context, get_llm_client


def test_openai_key_is_never_used_as_deepseek_fallback(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-secret")
    with pytest.raises(RAGConfigurationError, match="DEEPSEEK_API_KEY"):
        get_llm_client()


def test_context_respects_token_budget_and_prioritizes_chunks():
    sections = [{"text": "章节" * 5000, "metadata": {"book": "书", "chapter": "章"}}]
    chunks = [{"text": "关键段落" * 100, "metadata": {"book": "书", "chapter": "章"}}]
    context = format_context(sections, chunks, token_budget=300)
    assert "关键段落" in context
    assert rag_service._count_tokens(context) <= 300
