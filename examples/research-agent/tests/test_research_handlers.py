"""Tests for the fwh_anthropic-powered research agent.

The agent's domain steps are now FFL composed facets that call
``anthropic.messages.CreateMessage`` and hand the response text to
typed parser event facets. The handlers in this example are the
parsers — pure JSON-to-schema converters with deterministic fallbacks.

Two test surfaces:

1. **Parser utilities** (`extract_json_payload`, `coerce_*`,
   `synthetic_*`) — pure functions, exercised with hand-crafted
   inputs.
2. **FFL compilation** — the workflow file references
   ``anthropic.messages.*`` facets from fwh_anthropic, so we compile
   it against fwh_anthropic's messages.ffl as a library and assert
   structural counts.
"""

from __future__ import annotations

import json
import os

import pytest


# ---------------------------------------------------------------------------
# Parser utilities — JSON extraction and coercion
# ---------------------------------------------------------------------------


class TestExtractJsonPayload:
    def test_bare_json_object(self):
        from handlers.shared.research_utils import extract_json_payload

        assert extract_json_payload('{"x": 1}') == {"x": 1}

    def test_bare_json_array(self):
        from handlers.shared.research_utils import extract_json_payload

        assert extract_json_payload("[1, 2, 3]") == [1, 2, 3]

    def test_strips_code_fence(self):
        from handlers.shared.research_utils import extract_json_payload

        wrapped = 'Here is the data:\n```json\n{"a": 1, "b": [2, 3]}\n```\nDone.'
        assert extract_json_payload(wrapped) == {"a": 1, "b": [2, 3]}

    def test_strips_unlabelled_fence(self):
        from handlers.shared.research_utils import extract_json_payload

        wrapped = '```\n[{"id": "x"}]\n```'
        assert extract_json_payload(wrapped) == [{"id": "x"}]

    def test_finds_first_balanced_object(self):
        """Prose around a bare JSON object is stripped."""
        from handlers.shared.research_utils import extract_json_payload

        msg = 'Sure! The JSON is {"score": 87, "approved": true} — let me know.'
        assert extract_json_payload(msg) == {"score": 87, "approved": True}

    def test_finds_first_balanced_array(self):
        from handlers.shared.research_utils import extract_json_payload

        msg = "Here you go: [\"a\", \"b\"] and that's all."
        assert extract_json_payload(msg) == ["a", "b"]

    def test_empty_text_raises(self):
        from handlers.shared.research_utils import extract_json_payload

        with pytest.raises(ValueError, match="empty"):
            extract_json_payload("")

    def test_garbage_raises(self):
        from handlers.shared.research_utils import extract_json_payload

        with pytest.raises(ValueError, match="could not parse"):
            extract_json_payload("this is just prose with no json")


class TestCoercion:
    def test_coerce_topic_fills_defaults(self):
        from handlers.shared.research_utils import coerce_topic

        out = coerce_topic({"name": "x"}, topic_name="fallback", depth=3, max_subtopics=5)
        assert out["name"] == "x"
        assert out["depth"] == 3  # filled from default
        assert out["max_subtopics"] == 5

    def test_coerce_topic_synth_fallback_for_non_dict(self):
        from handlers.shared.research_utils import coerce_topic

        out = coerce_topic("not a dict", topic_name="t", depth=2, max_subtopics=3)
        assert out["name"] == "t"
        assert out["depth"] == 2
        assert out["max_subtopics"] == 3

    def test_coerce_subtopics_caps_count(self):
        from handlers.shared.research_utils import coerce_subtopics

        parsed = [{"name": f"s{i}", "description": f"d{i}", "priority": i} for i in range(10)]
        out = coerce_subtopics(parsed, parent_topic="P", max_subtopics=3)
        assert len(out) == 3
        assert all(s["parent_topic"] == "P" for s in out)

    def test_coerce_sources_synth_fallback(self):
        from handlers.shared.research_utils import coerce_sources

        out = coerce_sources(None, subtopic_name="s", max_sources=2)
        assert len(out) == 2

    def test_coerce_findings_keeps_only_dicts(self):
        from handlers.shared.research_utils import coerce_findings

        parsed = [
            {"claim": "a", "evidence": "b", "confidence": 0.8, "source_title": "t"},
            "not a finding",  # ignored
            {"claim": "c"},
        ]
        out = coerce_findings(parsed, subtopic_name="s")
        assert len(out) == 2
        assert out[0]["confidence"] == 0.8

    def test_coerce_analysis_synth_fallback(self):
        from handlers.shared.research_utils import coerce_analysis

        out = coerce_analysis(None, topic_name="t")
        assert "themes" in out
        assert 0.5 <= out["confidence_score"] <= 0.9

    def test_coerce_gaps_and_recs_uses_synth_when_empty(self):
        from handlers.shared.research_utils import coerce_gaps_and_recs

        out = coerce_gaps_and_recs({"gaps": [], "recommendations": []}, topic_name="t")
        # Synthetic fallback because both lists were empty.
        assert len(out["gaps"]) >= 1
        assert len(out["recommendations"]) >= 1

    def test_coerce_review_threshold(self):
        from handlers.shared.research_utils import coerce_review

        out = coerce_review({"score": 71}, topic_name="t")
        assert out["score"] == 71
        # Default approved derives from score when omitted.
        assert out["approved"] is True

    def test_coerce_review_explicit_approved(self):
        from handlers.shared.research_utils import coerce_review

        out = coerce_review({"score": 90, "approved": False}, topic_name="t")
        assert out["approved"] is False


# ---------------------------------------------------------------------------
# Parser handlers — exercise the dispatch + step_log path
# ---------------------------------------------------------------------------


class TestPlanningHandlers:
    def test_parse_topic_from_valid_json(self):
        from handlers.planning.planning_handlers import handle_parse_topic

        text = json.dumps(
            {
                "name": "climate adaptation",
                "depth": 4,
                "keywords": ["resilience", "policy"],
                "summary": "plan summary",
                "max_subtopics": 3,
            }
        )
        out = handle_parse_topic({"text": text, "topic_name": "climate adaptation",
                                  "depth": 4, "max_subtopics": 3})
        assert out["plan"]["name"] == "climate adaptation"
        assert out["plan"]["keywords"] == ["resilience", "policy"]

    def test_parse_topic_falls_back_on_garbage(self):
        from handlers.planning.planning_handlers import handle_parse_topic

        out = handle_parse_topic({"text": "I don't have JSON",
                                  "topic_name": "t", "depth": 2, "max_subtopics": 4})
        # Synthetic fallback still returns a valid Topic.
        assert out["plan"]["name"] == "t"
        assert out["plan"]["max_subtopics"] == 4

    def test_parse_subtopics_with_fence(self):
        from handlers.planning.planning_handlers import handle_parse_subtopics

        text = '```json\n[{"name": "a", "parent_topic": "P", "description": "d", "priority": 1}]\n```'
        out = handle_parse_subtopics({"text": text, "parent_topic": "P", "max_subtopics": 5})
        assert len(out["subtopics"]) == 1
        assert out["subtopics"][0]["name"] == "a"


class TestGatheringHandlers:
    def test_parse_sources_from_valid_json(self):
        from handlers.gathering.gathering_handlers import handle_parse_sources

        text = json.dumps(
            [
                {"title": "T1", "url": "u1", "relevance_score": 0.9, "source_type": "journal"},
                {"title": "T2", "url": "u2", "relevance_score": 0.7, "source_type": "book"},
            ]
        )
        out = handle_parse_sources(
            {"text": text, "subtopic_name": "s", "max_sources": 5}
        )
        assert len(out["sources"]) == 2
        assert out["sources"][0]["relevance_score"] == 0.9

    def test_parse_sources_caps_at_max(self):
        from handlers.gathering.gathering_handlers import handle_parse_sources

        sources = [{"title": f"S{i}", "url": f"u{i}",
                    "relevance_score": 0.5, "source_type": "web"} for i in range(20)]
        out = handle_parse_sources(
            {"text": json.dumps(sources), "subtopic_name": "s", "max_sources": 3}
        )
        assert len(out["sources"]) == 3

    def test_parse_findings_falls_back(self):
        from handlers.gathering.gathering_handlers import handle_parse_findings

        out = handle_parse_findings({"text": "no json here", "subtopic_name": "x"})
        assert isinstance(out["findings"], list)
        assert all("claim" in f for f in out["findings"])


class TestAnalysisHandlers:
    def test_parse_analysis_from_valid_json(self):
        from handlers.analysis.analysis_handlers import handle_parse_analysis

        text = json.dumps(
            {"themes": ["t1", "t2"], "contradictions": [], "gaps": ["g1"],
             "summary": "s", "confidence_score": 0.82}
        )
        out = handle_parse_analysis({"text": text, "topic_name": "T"})
        assert out["analysis"]["themes"] == ["t1", "t2"]
        assert out["analysis"]["confidence_score"] == 0.82

    def test_parse_gaps_returns_nested_pair(self):
        from handlers.analysis.analysis_handlers import handle_parse_gaps

        text = json.dumps(
            {
                "gaps": [{"description": "g1", "severity": "high", "area": "method"}],
                "recommendations": [
                    {"action": "do x", "priority": "high", "estimated_effort": "low"}
                ],
            }
        )
        out = handle_parse_gaps({"text": text, "topic_name": "T"})
        # ParseGaps schema returns `result` carrying both fields.
        assert "gaps" in out["result"]
        assert "recommendations" in out["result"]
        assert len(out["result"]["gaps"]) == 1


class TestWritingHandlers:
    def test_parse_draft_word_count_default(self):
        from handlers.writing.writing_handlers import handle_parse_draft

        text = json.dumps(
            {
                "title": "Report on X",
                "sections": [{"title": "Intro", "content": "one two three"}],
                "citations": [],
            }
        )
        out = handle_parse_draft({"text": text, "topic_name": "X"})
        # word_count derived when omitted.
        assert out["draft"]["word_count"] >= 3

    def test_parse_review_score(self):
        from handlers.writing.writing_handlers import handle_parse_review

        text = json.dumps(
            {"score": 78, "approved": True, "feedback": ["good"], "suggested_edits": []}
        )
        out = handle_parse_review({"text": text, "topic_name": "X"})
        assert out["review"]["score"] == 78
        assert out["review"]["approved"] is True


# ---------------------------------------------------------------------------
# Dispatch + registration
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_planning_dispatch(self):
        from handlers.planning.planning_handlers import _DISPATCH

        assert set(_DISPATCH.keys()) == {
            "research.Planning.ParseTopic",
            "research.Planning.ParseSubtopics",
        }

    def test_gathering_dispatch(self):
        from handlers.gathering.gathering_handlers import _DISPATCH

        assert set(_DISPATCH.keys()) == {
            "research.Gathering.ParseSources",
            "research.Gathering.ParseFindings",
        }

    def test_analysis_dispatch(self):
        from handlers.analysis.analysis_handlers import _DISPATCH

        assert set(_DISPATCH.keys()) == {
            "research.Analysis.ParseAnalysis",
            "research.Analysis.ParseGaps",
        }

    def test_writing_dispatch(self):
        from handlers.writing.writing_handlers import _DISPATCH

        assert set(_DISPATCH.keys()) == {
            "research.Writing.ParseDraft",
            "research.Writing.ParseReview",
        }

    def test_total_parser_count(self):
        from handlers.analysis.analysis_handlers import _DISPATCH as d3
        from handlers.gathering.gathering_handlers import _DISPATCH as d2
        from handlers.planning.planning_handlers import _DISPATCH as d1
        from handlers.writing.writing_handlers import _DISPATCH as d4

        # 8 parser facets, mirroring the 8 original domain facets.
        assert len(d1) + len(d2) + len(d3) + len(d4) == 8


# ---------------------------------------------------------------------------
# FFL compilation
# ---------------------------------------------------------------------------


class TestCompilation:
    @pytest.fixture()
    def parsed_ast(self):
        from facetwork.parser import FFLParser

        afl_path = os.path.join(
            os.path.dirname(__file__), "..", "ffl", "research.ffl"
        )
        with open(afl_path) as f:
            source = f.read()
        return FFLParser().parse(source)

    def test_afl_parses(self, parsed_ast):
        assert parsed_ast is not None

    def test_schema_count(self, parsed_ast):
        schemas = []
        for ns in parsed_ast.namespaces:
            schemas.extend(ns.schemas)
        # +1 over the original: GapsAndRecs (return shape for ParseGaps).
        assert len(schemas) == 8

    def test_event_facet_count_is_parsers_only(self, parsed_ast):
        event_facets = []
        for ns in parsed_ast.namespaces:
            event_facets.extend(ns.event_facets)
        # 8 typed parsers (one per old domain step). The old domain
        # facets are now composed `facet`s, not event facets.
        assert len(event_facets) == 8

    def test_composed_facet_count(self, parsed_ast):
        """The 8 old domain facets are now composed facets (`facet` not `event facet`)."""
        composed = []
        for ns in parsed_ast.namespaces:
            for f in ns.facets:
                # Skip the two mixin facets (Retry, Citation).
                if ns.name != "research.mixins":
                    composed.append(f)
        assert len(composed) == 8

    def test_no_prompt_blocks(self, parsed_ast):
        """Port removed all prompt blocks in favour of CreateMessage calls."""
        from facetwork.ast import PromptBlock

        count = 0
        for ns in parsed_ast.namespaces:
            for ef in ns.event_facets:
                if isinstance(ef.body, PromptBlock):
                    count += 1
            for f in ns.facets:
                if isinstance(f.body, PromptBlock):
                    count += 1
        assert count == 0

    def test_workflow_count(self, parsed_ast):
        workflows = []
        for ns in parsed_ast.namespaces:
            workflows.extend(ns.workflows)
        assert len(workflows) == 2

    def test_mixin_facet_count(self, parsed_ast):
        mixins_ns = [ns for ns in parsed_ast.namespaces if ns.name == "research.mixins"][0]
        assert len(mixins_ns.facets) == 2

    def test_implicit_count(self, parsed_ast):
        implicits = []
        for ns in parsed_ast.namespaces:
            implicits.extend(ns.implicits)
        assert len(implicits) == 2

    def test_foreach_present(self, parsed_ast):
        workflows_ns = [ns for ns in parsed_ast.namespaces if ns.name == "research.workflows"][0]
        deep_dive = [w for w in workflows_ns.workflows if w.sig.name == "DeepDive"][0]
        has_foreach = any(block.foreach is not None for block in deep_dive.body)
        assert has_foreach

    def test_references_anthropic_messages_namespace(self, parsed_ast):
        """The composed facets must `use anthropic.messages`."""
        target_namespaces = ["research.Planning", "research.Gathering",
                              "research.Analysis", "research.Writing"]
        for name in target_namespaces:
            ns = [n for n in parsed_ast.namespaces if n.name == name][0]
            uses = [str(u.name) for u in ns.uses]
            assert "anthropic.messages" in uses, (
                f"namespace {name} should `use anthropic.messages`"
            )
