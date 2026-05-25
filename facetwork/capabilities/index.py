"""Build and query a facet capability index from compiled FFL.

The input is a compiled program dict — either ``emit_dict(parse(source))`` or a
stored flow's ``compiled_ast`` — shaped as::

    {"type": "Program", "declarations": [
        {"type": "Namespace", "name": "osm.Spatial", "declarations": [
            {"type": "EventFacetDecl", "name": "WithinDistance",
             "doc": {"description": "..."},
             "params":  [{"name": "...", "type": "...", "default": {...}}],
             "returns": [{"name": "result", "type": "SpatialResult"}]},
            ...]},
        ...]}

Namespaces may nest; facets may also appear at the top level. The index is a
flat list of :class:`FacetCapability`, searchable by free text / namespace /
kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_FACET_TYPES = {"FacetDecl", "EventFacetDecl"}


@dataclass
class FacetParam:
    """One parameter or return value of a facet."""

    name: str
    type: str
    has_default: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = {"name": self.name, "type": self.type}
        if self.has_default:
            d["has_default"] = True
        return d


@dataclass
class FacetCapability:
    """A single facet's capability record."""

    qualified_name: str          # e.g. "osm.Spatial.WithinDistance"
    name: str                    # e.g. "WithinDistance"
    namespace: str               # e.g. "osm.Spatial" ("" for top-level)
    purpose: str                 # first line of the doc comment
    doc: str                     # full doc-comment description
    is_event: bool
    params: list[FacetParam] = field(default_factory=list)
    returns: list[FacetParam] = field(default_factory=list)
    mixins: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualified_name": self.qualified_name,
            "name": self.name,
            "namespace": self.namespace,
            "purpose": self.purpose,
            "is_event": self.is_event,
            "signature": self.signature,
            "params": [p.to_dict() for p in self.params],
            "returns": [r.to_dict() for r in self.returns],
            "mixins": self.mixins,
        }

    @property
    def signature(self) -> str:
        """A compact human-readable signature, e.g.
        ``osm.Spatial.WithinDistance(subject_path: String, …) => (result: SpatialResult)``."""
        ps = ", ".join(f"{p.name}: {p.type}" for p in self.params)
        rs = ", ".join(f"{r.name}: {r.type}" for r in self.returns)
        kw = "event facet " if self.is_event else "facet "
        return f"{kw}{self.qualified_name}({ps})" + (f" => ({rs})" if rs else "")


def _type_to_str(node: Any) -> str:
    """Render a type node (string, ``[T]`` array, or dict) as a string."""
    if node is None:
        return "Any"
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        t = node.get("type")
        if t in ("ArrayType", "Array"):
            elem = node.get("element") or node.get("elementType") or node.get("inner")
            return f"[{_type_to_str(elem)}]"
        return node.get("name") or node.get("type") or "Any"
    return str(node)


def _params(raw: list[dict] | None) -> list[FacetParam]:
    out: list[FacetParam] = []
    for p in raw or []:
        if not isinstance(p, dict):
            continue
        out.append(FacetParam(
            name=p.get("name", ""),
            type=_type_to_str(p.get("type")),
            has_default="default" in p and p.get("default") is not None,
        ))
    return out


def _first_line(text: str) -> str:
    for line in (text or "").splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def _facet_capability(decl: dict, namespace: str) -> FacetCapability:
    name = decl.get("name", "")
    qualified = f"{namespace}.{name}" if namespace else name
    doc = (decl.get("doc") or {}).get("description", "") if isinstance(decl.get("doc"), dict) else ""
    mixins = []
    for m in decl.get("mixins") or []:
        if isinstance(m, dict) and m.get("name"):
            mixins.append(m["name"])
    return FacetCapability(
        qualified_name=qualified,
        name=name,
        namespace=namespace,
        purpose=_first_line(doc),
        doc=doc,
        is_event=decl.get("type") == "EventFacetDecl",
        params=_params(decl.get("params")),
        returns=_params(decl.get("returns")),
        mixins=mixins,
    )


def _walk(decls: list, namespace: str, out: list[FacetCapability]) -> None:
    for decl in decls or []:
        if not isinstance(decl, dict):
            continue
        t = decl.get("type")
        if t == "Namespace":
            ns_name = decl.get("name", "")
            child_ns = f"{namespace}.{ns_name}" if namespace and ns_name else (ns_name or namespace)
            _walk(decl.get("declarations") or decl.get("body") or [], child_ns, out)
        elif t in _FACET_TYPES:
            out.append(_facet_capability(decl, namespace))


def index_program(program: dict) -> list[FacetCapability]:
    """Index every facet/event-facet in one compiled program dict."""
    if not isinstance(program, dict):
        return []
    out: list[FacetCapability] = []
    _walk(program.get("declarations") or [], "", out)
    return out


def index_programs(programs: list[dict]) -> list[FacetCapability]:
    """Index several programs, de-duplicating by qualified name (first wins)."""
    seen: dict[str, FacetCapability] = {}
    for prog in programs:
        for cap in index_program(prog):
            seen.setdefault(cap.qualified_name, cap)
    return sorted(seen.values(), key=lambda c: c.qualified_name)


def _score(cap: FacetCapability, terms: list[str]) -> int:
    """Relevance score for a capability against query terms (higher = better)."""
    if not terms:
        return 0
    name = cap.name.lower()
    qn = cap.qualified_name.lower()
    purpose = cap.purpose.lower()
    doc = cap.doc.lower()
    type_text = " ".join(p.type.lower() for p in cap.params + cap.returns)
    param_text = " ".join(p.name.lower() for p in cap.params + cap.returns)
    score = 0
    for term in terms:
        if term == name:
            score += 20
        elif term in name or term in qn:
            score += 10
        if term in purpose:
            score += 6
        elif term in doc:
            score += 3
        if term in type_text:
            score += 4
        if term in param_text:
            score += 2
    return score


def search(
    caps: list[FacetCapability],
    query: str = "",
    namespace: str = "",
    kind: str = "all",
    limit: int = 0,
) -> list[FacetCapability]:
    """Filter + rank capabilities.

    * ``query`` — free text matched (AND across whitespace-separated terms)
      against name / qualified name / purpose / doc / param+return names+types.
    * ``namespace`` — prefix match on the facet's namespace (e.g. ``osm.Spatial``
      or just ``osm``).
    * ``kind`` — ``"facet"`` | ``"event_facet"`` | ``"all"``.
    * ``limit`` — cap the result count (0 = no cap).

    Results are ranked by relevance when ``query`` is given, else by qualified name.
    """
    terms = [t for t in query.lower().split() if t]
    ns = namespace.lower().strip()
    result: list[tuple[int, FacetCapability]] = []
    for cap in caps:
        if kind == "facet" and cap.is_event:
            continue
        if kind == "event_facet" and not cap.is_event:
            continue
        if ns and not (cap.namespace.lower() == ns or cap.namespace.lower().startswith(ns + ".")):
            continue
        if terms:
            score = _score(cap, terms)
            # AND semantics: every term must hit something.
            if any(_score(cap, [t]) == 0 for t in terms):
                continue
            result.append((score, cap))
        else:
            result.append((0, cap))
    if terms:
        result.sort(key=lambda sc: (-sc[0], sc[1].qualified_name))
    else:
        result.sort(key=lambda sc: sc[1].qualified_name)
    ranked = [c for _, c in result]
    return ranked[:limit] if limit and limit > 0 else ranked
