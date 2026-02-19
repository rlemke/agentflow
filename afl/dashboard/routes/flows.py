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

"""Flow routes — list, detail, source, JSON, and run views."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..dependencies import get_store

router = APIRouter(prefix="/flows")


@router.get("")
def flow_list(request: Request, q: str | None = None, store=Depends(get_store)):
    """List all flows, optionally filtered by name search."""
    flows = store.get_all_flows()
    if q:
        flows = [f for f in flows if q.lower() in f.name.name.lower()]
    return request.app.state.templates.TemplateResponse(
        request,
        "flows/list.html",
        {"flows": flows, "search_query": q},
    )


@router.get("/{flow_id}")
def flow_detail(flow_id: str, request: Request, store=Depends(get_store)):
    """Show flow detail with workflows."""
    flow = store.get_flow(flow_id)
    workflows = store.get_workflows_by_flow(flow_id) if flow else []
    runners = []
    if flow:
        for wf in flow.workflows:
            runners.extend(store.get_runners_by_workflow(wf.uuid))
        runners.sort(key=lambda r: r.start_time, reverse=True)
        runners = runners[:20]
    return request.app.state.templates.TemplateResponse(
        request,
        "flows/detail.html",
        {"flow": flow, "workflows": workflows, "runners": runners},
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


@router.get("/{flow_id}/run/{workflow_id}")
def flow_run_form(
    flow_id: str,
    workflow_id: str,
    request: Request,
    store=Depends(get_store),
):
    """Show parameter input form for running a workflow from a flow."""
    import json

    flow = store.get_flow(flow_id)
    if not flow:
        return request.app.state.templates.TemplateResponse(
            request,
            "flows/detail.html",
            {"flow": None, "workflows": [], "runners": []},
        )
    workflow_def = store.get_workflow(workflow_id)
    workflow_name = workflow_def.name if workflow_def else "Unknown"
    params: list[dict] = []
    parse_error = None

    if flow.compiled_sources:
        try:
            from afl.emitter import JSONEmitter
            from afl.parser import AFLParser
            from afl.runtime.submit import _find_workflow_in_program

            parser = AFLParser()
            source_text = flow.compiled_sources[0].content
            ast = parser.parse(source_text)
            emitter = JSONEmitter(include_locations=False)
            program_json = emitter.emit(ast)
            program_dict = json.loads(program_json)

            wf_ast = _find_workflow_in_program(program_dict, workflow_name)
            if wf_ast:
                for p in wf_ast.get("params", []):
                    default_val = p.get("default")
                    if isinstance(default_val, dict) and "value" in default_val:
                        default_val = default_val["value"]
                    params.append(
                        {
                            "name": p.get("name", ""),
                            "type": p.get("type", ""),
                            "default": default_val,
                        }
                    )
        except Exception as exc:
            parse_error = str(exc)

    return request.app.state.templates.TemplateResponse(
        request,
        "flows/run.html",
        {
            "flow": flow,
            "workflow_def": workflow_def,
            "workflow_name": workflow_name,
            "params": params,
            "parse_error": parse_error,
        },
    )


@router.post("/{flow_id}/run/{workflow_id}")
def flow_run_execute(
    flow_id: str,
    workflow_id: str,
    request: Request,
    inputs_json: str = Form("{}"),
    store=Depends(get_store),
):
    """Execute a workflow from an existing flow — creates only Runner + Task."""
    import json
    import time

    from afl.emitter import JSONEmitter
    from afl.parser import AFLParser
    from afl.runtime.entities import (
        RunnerDefinition,
        RunnerState,
        TaskDefinition,
        TaskState,
    )
    from afl.runtime.submit import _find_workflow_in_program
    from afl.runtime.types import generate_id

    flow = store.get_flow(flow_id)
    workflow_def = store.get_workflow(workflow_id) if flow else None

    if not flow or not workflow_def:
        return request.app.state.templates.TemplateResponse(
            request,
            "flows/detail.html",
            {"flow": flow, "workflows": [], "runners": []},
        )

    # Extract defaults from compiled AST
    inputs: dict = {}
    if flow.compiled_sources:
        try:
            parser = AFLParser()
            source_text = flow.compiled_sources[0].content
            ast = parser.parse(source_text)
            emitter = JSONEmitter(include_locations=False)
            program_json = emitter.emit(ast)
            program_dict = json.loads(program_json)

            wf_ast = _find_workflow_in_program(program_dict, workflow_def.name)
            if wf_ast:
                for param in wf_ast.get("params", []):
                    default_val = param.get("default")
                    if default_val is not None:
                        if isinstance(default_val, dict) and "value" in default_val:
                            inputs[param["name"]] = default_val["value"]
                        else:
                            inputs[param["name"]] = default_val
        except Exception:
            pass

    # Override with user-provided inputs from form
    try:
        user_inputs = json.loads(inputs_json) if inputs_json else {}
        inputs.update(user_inputs)
    except (json.JSONDecodeError, ValueError):
        pass

    # Create only Runner + Task — reuse existing Flow + Workflow
    now_ms = int(time.time() * 1000)
    runner_id = generate_id()
    task_id = generate_id()

    runner = RunnerDefinition(
        uuid=runner_id,
        workflow_id=workflow_id,
        workflow=workflow_def,
        state=RunnerState.CREATED,
    )
    store.save_runner(runner)

    task = TaskDefinition(
        uuid=task_id,
        name="afl:execute",
        runner_id=runner_id,
        workflow_id=workflow_id,
        flow_id=flow_id,
        step_id="",
        state=TaskState.PENDING,
        created=now_ms,
        updated=now_ms,
        task_list_name="default",
        data={
            "flow_id": flow_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow_def.name,
            "inputs": inputs,
            "runner_id": runner_id,
        },
    )
    store.save_task(task)

    return RedirectResponse(
        url=f"/runners/{runner_id}",
        status_code=303,
    )
