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

"""Flow routes — list, detail, source, JSON views."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..dependencies import get_store

router = APIRouter(prefix="/flows")


@router.get("")
def flow_list(request: Request, store=Depends(get_store)):
    """List all flows."""
    flows = store.get_all_flows()
    return request.app.state.templates.TemplateResponse(
        request,
        "flows/list.html",
        {"flows": flows},
    )


@router.get("/{flow_id}")
def flow_detail(flow_id: str, request: Request, store=Depends(get_store)):
    """Show flow detail with workflows."""
    flow = store.get_flow(flow_id)
    workflows = store.get_workflows_by_flow(flow_id) if flow else []
    return request.app.state.templates.TemplateResponse(
        request,
        "flows/detail.html",
        {"flow": flow, "workflows": workflows},
    )


@router.get("/{flow_id}/source")
def flow_source(flow_id: str, request: Request, store=Depends(get_store)):
    """Show AFL source code for a flow."""
    flow = store.get_flow(flow_id)
    sources = flow.compiled_sources if flow else []
    return request.app.state.templates.TemplateResponse(
        request,
        "flows/source.html",
        {"flow": flow, "sources": sources},
    )


@router.get("/{flow_id}/json")
def flow_json(flow_id: str, request: Request, store=Depends(get_store)):
    """Parse AFL source and show the compiled JSON output."""
    flow = store.get_flow(flow_id)
    json_output = None
    parse_error = None

    if flow and flow.compiled_sources:
        try:
            from afl.emitter import JSONEmitter
            from afl.parser import AFLParser

            parser = AFLParser()
            source_text = flow.compiled_sources[0].content
            ast = parser.parse(source_text)
            emitter = JSONEmitter(indent=2)
            json_output = emitter.emit(ast)
        except Exception as exc:
            parse_error = str(exc)

    return request.app.state.templates.TemplateResponse(
        request,
        "flows/json.html",
        {
            "flow": flow,
            "json_output": json_output,
            "parse_error": parse_error,
        },
    )
