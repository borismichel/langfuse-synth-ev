"""Prefix-aware playground links (LAN-357).

The portal serves live deployments behind ``/live/{id}/…`` and injects
``LIVE_BASE_PATH=/live/{id}`` into the container. Every internal href/form-action must
carry that prefix; with the env unset, rendered output must be byte-identical to today.
Routes themselves never move — this only affects link *generation*.
"""
import pytest

from synth.live import app as evapp
from synth.live.paths import base_path, local


def test_base_path_unset_is_empty(monkeypatch):
    monkeypatch.delenv("LIVE_BASE_PATH", raising=False)
    assert base_path() == ""
    assert local("/") == "/"
    assert local("/submit") == "/submit"


def test_local_prefixes_every_internal_path(monkeypatch):
    monkeypatch.setenv("LIVE_BASE_PATH", "/live/x")
    assert local("/") == "/live/x/"
    assert local("/submit") == "/live/x/submit"
    assert local("/analytics") == "/live/x/analytics"


def test_local_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("LIVE_BASE_PATH", "/live/x/")
    assert local("/submit") == "/live/x/submit"


def test_form_and_error_links_are_bare_when_unset(monkeypatch):
    monkeypatch.delenv("LIVE_BASE_PATH", raising=False)
    form = evapp._form("{}")
    err = evapp._error_card("oops", ValueError("y"))
    assert 'action="/submit"' in form
    assert 'href="/"' in err
    assert "/live/" not in form and "/live/" not in err


def test_form_and_error_links_carry_prefix(monkeypatch):
    monkeypatch.setenv("LIVE_BASE_PATH", "/live/x")
    form = evapp._form("{}")
    err = evapp._error_card("oops", ValueError("y"))
    assert 'action="/live/x/submit"' in form
    assert 'action="/submit"' not in form
    assert 'href="/live/x/"' in err


def test_index_page_byte_identical_when_unset(monkeypatch):
    """Full rendered index page must be identical whether the env is unset or empty —
    proof that the default path is unchanged behaviour (external URLs untouched)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from synth.config import load_config

    cfg = load_config("config/demo.yaml")

    monkeypatch.delenv("LIVE_BASE_PATH", raising=False)
    bare = TestClient(evapp.create_app(cfg)).get("/").text
    monkeypatch.setenv("LIVE_BASE_PATH", "")
    empty = TestClient(evapp.create_app(cfg)).get("/").text
    assert bare == empty
    assert "/live/" not in bare
    assert 'action="/submit"' in bare and "href='/analytics'" in bare


def test_index_page_prefixed(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from synth.config import load_config

    cfg = load_config("config/demo.yaml")
    monkeypatch.setenv("LIVE_BASE_PATH", "/live/x")
    text = TestClient(evapp.create_app(cfg)).get("/").text
    assert 'action="/live/x/submit"' in text
    assert "href='/live/x/analytics'" in text
