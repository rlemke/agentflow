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

"""Workflow creation routes — new, compile, run."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..dependencies import get_store

router = APIRouter(prefix="/workflows")


@router.get("/new")
def workflow_new(request: Request):
    """Render the new workflow form."""
    return request.app.state.templates.TemplateResponse(
        request,
        "workflows/new.html",
        {},
    )


@router.post("/validate")
def workflow_validate(request: Request, source: str = Form(...)):
    """Validate AFL source without compiling."""
    errors: list[dict] = []
    namespaces: list[str] = []
    facets: list[str] = []
    workflows: list[str] = []

    try:
        from afl.parser import AFLParser
        from afl.validator import AFLValidator

        parser = AFLParser()
        ast = parser.parse(source)

        # Validate
        validator = AFLValidator()
        validation_result = validator.validate(ast)
        for err in validation_result.errors:
            errors.append(
                {
                    "message": err.message,
                    "line": getattr(err, "line", None),
                    "column": getattr(err, "column", None),
                }
            )

        # Extract AST summary
        for ns in ast.namespaces:
            namespaces.append(ns.name)
            for f in ns.facets:
                facets.append(f"{ns.name}.{f.name}")
            for w in ns.workflows:
                workflows.append(f"{ns.name}.{w.name}")
        for node in ast.facets:
            facets.append(node.name)
        for node in ast.workflows:
            workflows.append(node.name)

    except Exception as exc:
        errors.append({"message": str(exc), "line": None, "column": None})

    return request.app.state.templates.TemplateResponse(
        request,
        "workflows/validate.html",
        {
            "source": source,
            "errors": errors,
            "namespaces": namespaces,
            "facets": facets,
            "workflows": workflows,
        },
    )


@router.post("/compile")
def workflow_compile(request: Request, source: str = Form(...)):
    """Compile AFL source and show available workflows."""
    errors: list[dict] = []
    workflows: list[dict] = []

    try:
        from afl.emitter import JSONEmitter
        from afl.parser import AFLParser
        from afl.validator import AFLValidator

        parser = AFLParser()
        ast = parser.parse(source)

        # Validate
        validator = AFLValidator()
        validation_result = validator.validate(ast)
        for err in validation_result.errors:
            errors.append(
                {
                    "message": err.message,
                    "line": getattr(err, "line", None),
                    "column": getattr(err, "column", None),
                }
            )

        # Emit to JSON and extract workflows
        emitter = JSONEmitter(include_locations=False)
        program_json = emitter.emit(ast)
        from afl.ast_utils import find_all_workflows

        program_dict = json.loads(program_json)

        for wf in find_all_workflows(program_dict):
            params_with_defaults = []
            for p in wf.get("params", []):
                default_val = p.get("default")
                # Extract the raw value from emitter's literal dict format
                if isinstance(default_val, dict) and "value" in default_val:
                    default_val = default_val["value"]
                params_with_defaults.append(
                    {
                        "name": p.get("name", ""),
                        "type": p.get("type", ""),
                        "default": default_val,
                    }
                )
            workflows.append(
                {
                    "name": wf.get("name", ""),
                    "params": params_with_defaults,
                }
            )

    except Exception as exc:
        errors.append({"message": str(exc), "line": None, "column": None})

    return request.app.state.templates.TemplateResponse(
        request,
        "workflows/compile.html",
        {
            "source": source,
            "errors": errors,
            "workflows": workflows,
        },
    )


@router.post("/run")
def workflow_run(
    request: Request,
    source: str = Form(...),
    workflow_name: str = Form(...),
    inputs_json: str = Form("{}"),
    store=Depends(get_store),
):
    """Compile, save, and queue a workflow for execution."""
    from afl.emitter import JSONEmitter
    from afl.parser import AFLParser
    from afl.runtime.entities import (
        FlowDefinition,
        FlowIdentity,
        RunnerDefinition,
        RunnerState,
        SourceText,
        TaskDefinition,
        TaskState,
        WorkflowDefinition,
    )
    from afl.runtime.types import generate_id

    # Parse and compile
    parser = AFLParser()
    ast = parser.parse(source)
    emitter = JSONEmitter(include_locations=False)
    program_json = emitter.emit(ast)
    from afl.ast_utils import find_workflow

    program_dict = json.loads(program_json)

    # Extract input values: start with defaults from the compiled AST

    inputs: dict = {}
    wf_ast = find_workflow(program_dict, workflow_name)
    if wf_ast:
        for param in wf_ast.get("params", []):
            default_val = param.get("default")
            if default_val is not None:
                if isinstance(default_val, dict) and "value" in default_val:
                    inputs[param["name"]] = default_val["value"]
                else:
                    inputs[param["name"]] = default_val

    # Override with user-provided inputs from form
    try:
        user_inputs = json.loads(inputs_json) if inputs_json else {}
        inputs.update(user_inputs)
    except (json.JSONDecodeError, ValueError):
        pass

    # Create entities
    now_ms = int(time.time() * 1000)
    flow_id = generate_id()
    wf_id = generate_id()
    runner_id = generate_id()
    task_id = generate_id()

    flow = FlowDefinition(
        uuid=flow_id,
        name=FlowIdentity(name=workflow_name, path="dashboard", uuid=flow_id),
        compiled_sources=[SourceText(name="source.afl", content=source)],
    )
    store.save_flow(flow)

    workflow = WorkflowDefinition(
        uuid=wf_id,
        name=workflow_name,
        namespace_id="dashboard",
        facet_id=wf_id,
        flow_id=flow_id,
        starting_step="",
        version="1.0",
        date=now_ms,
    )
    store.save_workflow(workflow)

    runner = RunnerDefinition(
        uuid=runner_id,
        workflow_id=wf_id,
        workflow=workflow,
        state=RunnerState.CREATED,
    )
    store.save_runner(runner)

    task = TaskDefinition(
        uuid=task_id,
        name="afl:execute",
        runner_id=runner_id,
        workflow_id=wf_id,
        flow_id=flow_id,
        step_id="",
        state=TaskState.PENDING,
        created=now_ms,
        updated=now_ms,
        task_list_name="default",
        data={
            "flow_id": flow_id,
            "workflow_name": workflow_name,
            "inputs": inputs,
            "runner_id": runner_id,
        },
    )
    store.save_task(task)

    return RedirectResponse(
        url=f"/runners/{runner_id}",
        status_code=303,
    )
