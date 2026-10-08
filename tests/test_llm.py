"""LLM seam: provider resolution + prompt quality gates. No network."""

from __future__ import annotations

import os

from telemarketer.consent import CampaignConfig, Contact
from telemarketer.llm import (MockLLM, PROVIDERS, build_sales_system_prompt,
                              resolve_provider)


def _contact():
    return Contact.from_dict({"name": "Jo", "phone": "+1", "consent_proof": "f:1",
                              "consent_date": "2026-01-01", "source": "test"})


def test_resolve_falls_back_to_mock(monkeypatch):
    for spec in PROVIDERS.values():
        monkeypatch.delenv(spec["env"], raising=False)
    provider, name = resolve_provider()
    assert name == "mock"
    assert isinstance(provider, MockLLM)


def test_resolve_prefers_explicit(monkeypatch):
    for spec in PROVIDERS.values():
        monkeypatch.delenv(spec["env"], raising=False)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    _, name = resolve_provider("xai")
    assert name == "xai"


def test_mockllm_pops_then_repeats_default():
    m = MockLLM(["one", "two"], default="done")
    assert m.chat([]) == "one"
    assert m.chat([]) == "two"
    assert m.chat([]) == "done"
    assert len(m.calls) == 3


def test_system_prompt_encodes_human_grade_rules():
    p = build_sales_system_prompt(
        CampaignConfig(agent_name="Sam", client_name="Acme"), _contact())
    assert "Sam" in p and "Acme" in p
    assert "25 words" in p            # short turns
    assert "backchannels" in p.lower()
    assert "AI" in p                  # truthfulness about being an AI
    assert "one soft reframe" in p.lower()
    assert "END_CALL" in p            # knows when to stop
