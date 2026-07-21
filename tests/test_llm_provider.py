"""Provider-layer routing (LAN-378): default Anthropic, opt-in OpenAI, model resolution."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from synth import llm


def test_default_provider_is_anthropic(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm.resolve_provider() == "anthropic"


def test_openai_opt_in_and_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "OpenAI")
    assert llm.resolve_provider() == "openai"


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(ValueError):
        llm.resolve_provider()


def test_model_resolution_precedence(monkeypatch):
    # LLM_MODEL wins over a caller default.
    monkeypatch.setenv("LLM_MODEL", "override-x")
    assert llm.resolve_model("anthropic", "caller-default") == "override-x"
    # Falls back to the caller default, then the provider built-in.
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.resolve_model("anthropic", "caller-default") == "caller-default"
    assert llm.resolve_model("openai") == "gpt-4o"


def test_get_llm_default_keeps_caller_model_for_anthropic(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = llm.get_llm("claude-sonnet-4-6")
    assert (client.provider, client.model) == ("anthropic", "claude-sonnet-4-6")


def test_get_llm_openai_ignores_anthropic_caller_model(monkeypatch):
    # An Anthropic-config model id must not leak to OpenAI; fall back to its default.
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = llm.get_llm("claude-sonnet-4-6")
    assert (client.provider, client.model) == ("openai", "gpt-4o")


def test_complete_routes_to_anthropic_shape():
    client = llm.LLMClient("anthropic", "claude-sonnet-4-6")
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")],
            usage=SimpleNamespace(input_tokens=11, output_tokens=3),
        )

    client._impl = SimpleNamespace(messages=SimpleNamespace(create=create))
    res = client.complete(system="S", messages=[{"role": "user", "content": "hi"}])
    assert (res.text, res.input_tokens, res.output_tokens) == ("ok", 11, 3)
    assert captured["system"] == "S"  # Anthropic keeps system separate


def test_complete_routes_to_openai_shape():
    client = llm.LLMClient("openai", "gpt-4o")
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=3),
        )

    client._impl = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    res = client.complete(system="S", messages=[{"role": "user", "content": "hi"}])
    assert (res.text, res.input_tokens, res.output_tokens) == ("ok", 11, 3)
    # OpenAI folds the system prompt into a leading message role.
    assert captured["messages"][0] == {"role": "system", "content": "S"}
    assert captured["messages"][1] == {"role": "user", "content": "hi"}
