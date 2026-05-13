"""Tests for workflow→task_list routing."""

from __future__ import annotations

import pytest

from facetwork.runtime.task_list_routing import (
    DEFAULT_TASK_LIST,
    ENV_VAR,
    parse_map,
    resolve_task_list,
)


def test_resolve_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert resolve_task_list("osm.AnalyzeRegion") == DEFAULT_TASK_LIST


def test_resolve_returns_explicit_default(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert resolve_task_list("anything", default="custom") == "custom"


def test_resolve_exact_prefix(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "osm.=osm,anthropic.=anthropic")
    assert resolve_task_list("osm.AnalyzeRegion") == "osm"
    assert resolve_task_list("anthropic.AskClaude") == "anthropic"
    assert resolve_task_list("other.Workflow") == DEFAULT_TASK_LIST


def test_resolve_longest_prefix_wins(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "osm.=osm,osm.heavy.=osm-heavy")
    assert resolve_task_list("osm.heavy.PBFImport") == "osm-heavy"
    assert resolve_task_list("osm.AnalyzeRegion") == "osm"


def test_resolve_empty_prefix_sets_global_fallback(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "osm.=osm,=catchall")
    assert resolve_task_list("osm.X") == "osm"
    assert resolve_task_list("unrelated.X") == "catchall"


def test_parse_map_skips_malformed_entries():
    pairs = parse_map("osm.=osm,malformed,=,empty=,=alsoempty,foo=bar")
    assert ("malformed", "") not in pairs
    # empty task list rejected
    assert all(tl != "" for _, tl in pairs)
    # valid entries kept
    assert ("osm.", "osm") in pairs
    assert ("foo", "bar") in pairs


def test_parse_map_trims_whitespace():
    pairs = parse_map(" osm. = osm , anthropic. = anthropic ")
    assert ("osm.", "osm") in pairs
    assert ("anthropic.", "anthropic") in pairs


@pytest.mark.parametrize(
    "name,expected",
    [
        ("", DEFAULT_TASK_LIST),
        ("osm", DEFAULT_TASK_LIST),  # "osm" alone doesn't match "osm." prefix
        ("osm.X", "osm"),
    ],
)
def test_resolve_edge_cases(monkeypatch, name, expected):
    monkeypatch.setenv(ENV_VAR, "osm.=osm")
    assert resolve_task_list(name) == expected
