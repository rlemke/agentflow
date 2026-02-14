# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Namespace browser routes."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, Request

from ..dependencies import get_store

router = APIRouter(prefix="/namespaces")


@dataclass
class NamespaceSummary:
    """Aggregated namespace info across flows."""

    name: str
    flow_count: int = 0
    facet_count: int = 0
    workflow_count: int = 0
    facets: list = field(default_factory=list)
    workflows: list = field(default_factory=list)


def _aggregate_namespaces(store) -> dict[str, NamespaceSummary]:
    """Aggregate namespace data from all flows."""
    flows = store.get_all_flows()
    ns_map: dict[str, NamespaceSummary] = {}

    for flow in flows:
        seen_in_flow: set[str] = set()
        for ns in flow.namespaces:
            if ns.name not in ns_map:
                ns_map[ns.name] = NamespaceSummary(name=ns.name)
            if ns.name not in seen_in_flow:
                ns_map[ns.name].flow_count += 1
                seen_in_flow.add(ns.name)

        for facet in flow.facets:
            ns_id = facet.namespace_id
            # Find namespace name by ID
            ns_name = _resolve_ns_name(flow, ns_id)
            if ns_name and ns_name in ns_map:
                ns_map[ns_name].facet_count += 1
                ns_map[ns_name].facets.append(facet)

        for wf in flow.workflows:
            ns_id = wf.namespace_id
            ns_name = _resolve_ns_name(flow, ns_id)
            if ns_name and ns_name in ns_map:
                ns_map[ns_name].workflow_count += 1
                ns_map[ns_name].workflows.append(wf)

    return ns_map


def _resolve_ns_name(flow, ns_id: str) -> str | None:
    """Resolve a namespace ID to its name within a flow."""
    for ns in flow.namespaces:
        if ns.uuid == ns_id:
            return ns.name
    return None


@router.get("")
def namespace_list(request: Request, store=Depends(get_store)):
    """List all namespaces aggregated across flows."""
    ns_map = _aggregate_namespaces(store)
    namespaces = sorted(ns_map.values(), key=lambda n: n.name)
    return request.app.state.templates.TemplateResponse(
        request,
        "namespaces/list.html",
        {"namespaces": namespaces},
    )


@router.get("/{namespace_name:path}")
def namespace_detail(namespace_name: str, request: Request, store=Depends(get_store)):
    """Show namespace detail with facets and workflows."""
    ns_map = _aggregate_namespaces(store)
    namespace = ns_map.get(namespace_name)
    return request.app.state.templates.TemplateResponse(
        request,
        "namespaces/detail.html",
        {"namespace": namespace},
    )
