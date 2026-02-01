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

"""Claude agent runner for AFL workflow execution.

Wraps the Evaluator to automatically dispatch event facets to Claude
via the Anthropic API with tool use, or to custom registered handlers.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .evaluator import Evaluator, ExecutionResult, ExecutionStatus
from .persistence import PersistenceAPI
from .states import StepState
from .step import StepDefinition

try:
    import anthropic  # noqa: F401

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# Mapping from AFL type names to JSON Schema types
AFL_TYPE_MAP: dict[str, dict] = {
    "Long": {"type": "integer"},
    "Int": {"type": "integer"},
    "Double": {"type": "number"},
    "String": {"type": "string"},
    "Boolean": {"type": "boolean"},
    "List": {"type": "array"},
    "Map": {"type": "object"},
}


@dataclass
class ToolDefinition:
    """Definition of a tool derived from an EventFacetDecl.

    The tool's input_schema is built from the facet's returns (what Claude produces).
    The facet's params provide context for Claude's message.
    """

    name: str
    description: str
    input_schema: dict
    param_names: list[str]
    return_names: list[str]


class ToolRegistry:
    """Registry of custom handlers for event facet types.

    Mirrors the LocalEventHandler pattern but supports a default fallback handler.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict], dict]] = {}
        self._default_handler: Callable[[str, dict], dict] | None = None

    def register(self, event_type: str, handler: Callable[[dict], dict]) -> None:
        """Register a handler for a specific event facet type.

        Args:
            event_type: The event facet name
            handler: Function (payload) -> result dict
        """
        self._handlers[event_type] = handler

    def set_default_handler(self, handler: Callable[[str, dict], dict]) -> None:
        """Set a fallback handler for unregistered event types.

        Args:
            handler: Function (event_type, payload) -> result dict
        """
        self._default_handler = handler

    def has_handler(self, event_type: str) -> bool:
        """Check if a specific or default handler exists."""
        return event_type in self._handlers or self._default_handler is not None

    def handle(self, event_type: str, payload: dict) -> dict | None:
        """Dispatch to registered handler, then default, or return None.

        Args:
            event_type: The event facet name
            payload: Parameter values for the event

        Returns:
            Result dict, or None if no handler available
        """
        handler = self._handlers.get(event_type)
        if handler is not None:
            return handler(payload)
        if self._default_handler is not None:
            return self._default_handler(event_type, payload)
        return None


class ClaudeAgentRunner:
    """Runs AFL workflows, dispatching event facets to Claude or custom handlers.

    Usage:
        store = MemoryStore()
        evaluator = Evaluator(persistence=store)
        runner = ClaudeAgentRunner(
            evaluator=evaluator,
            persistence=store,
            anthropic_client=anthropic.Anthropic(),
        )
        result = runner.run(workflow_ast, inputs={"x": 1}, program_ast=program_ast)
    """

    def __init__(
        self,
        evaluator: Evaluator,
        persistence: PersistenceAPI,
        *,
        anthropic_client: Any = None,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: str | None = None,
        tool_registry: ToolRegistry | None = None,
        max_dispatches: int = 100,
    ) -> None:
        self.evaluator = evaluator
        self.persistence = persistence
        self.anthropic_client = anthropic_client
        self.model = model
        self.system_prompt = system_prompt
        self.tool_registry = tool_registry or ToolRegistry()
        self.max_dispatches = max_dispatches

    def run(
        self,
        workflow_ast: dict,
        inputs: dict | None = None,
        program_ast: dict | None = None,
        *,
        task_description: str | None = None,
    ) -> ExecutionResult:
        """Execute a workflow end-to-end, dispatching event facets as needed.

        Args:
            workflow_ast: Compiled workflow AST
            inputs: Optional input parameter values
            program_ast: Optional program AST for facet lookups
            task_description: Optional description for Claude's context

        Returns:
            ExecutionResult with outputs or error
        """
        # Extract tool definitions from program AST
        tool_defs = self._extract_tool_definitions(program_ast)
        claude_tools = [self._to_anthropic_tool(td) for td in tool_defs]

        # Initial execution
        result = self.evaluator.execute(workflow_ast, inputs, program_ast)

        dispatch_count = 0
        workflow_name = workflow_ast.get("name", "unknown")

        while result.status == ExecutionStatus.PAUSED and dispatch_count < self.max_dispatches:
            # Find steps blocked at EVENT_TRANSMIT
            blocked_steps = self._find_blocked_steps(result.workflow_id)
            if not blocked_steps:
                break

            for step in blocked_steps:
                dispatch_count += 1
                if dispatch_count > self.max_dispatches:
                    break

                step_result = self._dispatch_single_step(
                    step,
                    claude_tools=claude_tools,
                    tool_defs=tool_defs,
                    workflow_name=workflow_name,
                    task_description=task_description,
                )
                self.evaluator.continue_step(step.id, step_result)

            # Resume evaluation
            result = self.evaluator.resume(
                result.workflow_id,
                workflow_ast,
                program_ast,
                inputs,
            )

        return result

    def _find_blocked_steps(self, workflow_id: str) -> list[StepDefinition]:
        """Find steps blocked at EVENT_TRANSMIT for a workflow."""
        all_steps = self.persistence.get_steps_by_workflow(workflow_id)
        return [s for s in all_steps if s.state == StepState.EVENT_TRANSMIT and not s.is_terminal]

    def _dispatch_single_step(
        self,
        step: StepDefinition,
        *,
        claude_tools: list[dict],
        tool_defs: list[ToolDefinition],
        workflow_name: str,
        task_description: str | None,
    ) -> dict:
        """Dispatch a single blocked step via custom handler or Claude.

        Returns:
            Result dict to pass to continue_step
        """
        # Build payload from step params
        payload = {name: attr.value for name, attr in step.attributes.params.items()}

        # Try custom handler first
        custom_result = self.tool_registry.handle(step.facet_name, payload)
        if custom_result is not None:
            return custom_result

        # Fall back to Claude API
        if self.anthropic_client is None:
            if not HAS_ANTHROPIC:
                raise RuntimeError(
                    f"No handler registered for event facet '{step.facet_name}' "
                    "and the anthropic package is not installed. "
                    "Install it with: pip install anthropic"
                )
            raise RuntimeError(
                f"No handler registered for event facet '{step.facet_name}' "
                "and no anthropic_client was provided."
            )

        return self._call_claude(
            step=step,
            payload=payload,
            claude_tools=claude_tools,
            tool_defs=tool_defs,
            workflow_name=workflow_name,
            task_description=task_description,
        )

    def _call_claude(
        self,
        *,
        step: StepDefinition,
        payload: dict,
        claude_tools: list[dict],
        tool_defs: list[ToolDefinition],
        workflow_name: str,
        task_description: str | None,
    ) -> dict:
        """Make a single Claude API call for an event facet step.

        Returns:
            Result dict from Claude's tool_use response
        """
        system = self.system_prompt or (
            f"You are an agent in workflow '{workflow_name}'. Use tools to complete tasks."
        )

        # Build user message with context
        parts = [f"Workflow: {workflow_name}"]
        if task_description:
            parts.append(f"Task: {task_description}")
        parts.append(f"Event facet: {step.facet_name}")
        parts.append(f"Parameters: {payload}")
        parts.append("Please use the appropriate tool to provide the result.")
        user_message = "\n".join(parts)

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            tools=claude_tools,
        )

        # Extract tool_use result matching the facet name
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == step.facet_name:
                return block.input

        # No matching tool_use found — return empty result
        return {}

    def _extract_tool_definitions(self, program_ast: dict | None) -> list[ToolDefinition]:
        """Extract ToolDefinitions from EventFacetDecl nodes in the program AST."""
        if not program_ast:
            return []
        declarations = program_ast.get("declarations", [])
        return self._search_for_event_facets(declarations)

    def _search_for_event_facets(self, declarations: list) -> list[ToolDefinition]:
        """Recursively search declarations for EventFacetDecl nodes."""
        results: list[ToolDefinition] = []
        for decl in declarations:
            decl_type = decl.get("type", "")
            if decl_type == "EventFacetDecl":
                results.append(self._build_tool_definition(decl))
            elif decl_type == "Namespace":
                nested = decl.get("declarations", [])
                results.extend(self._search_for_event_facets(nested))
        return results

    def _build_tool_definition(self, decl: dict) -> ToolDefinition:
        """Build a ToolDefinition from an EventFacetDecl dict."""
        name = decl.get("name", "")
        params = decl.get("params", [])
        returns = decl.get("returns", [])

        param_names = [p.get("name", "") for p in params]
        return_names = [r.get("name", "") for r in returns]

        # Build JSON Schema properties from returns (what Claude fills in)
        properties: dict[str, dict] = {}
        for ret in returns:
            ret_name = ret.get("name", "")
            ret_type = ret.get("type", "String")
            properties[ret_name] = AFL_TYPE_MAP.get(ret_type, {"type": "string"})

        # Build description with param info
        param_desc = ", ".join(f"{p.get('name', '')}: {p.get('type', 'Any')}" for p in params)
        description = f"Process {name}."
        if param_desc:
            description += f" Parameters: {param_desc}."
        description += " Return the result values."

        return ToolDefinition(
            name=name,
            description=description,
            input_schema={
                "type": "object",
                "properties": properties,
                "required": return_names,
            },
            param_names=param_names,
            return_names=return_names,
        )

    def _to_anthropic_tool(self, tool_def: ToolDefinition) -> dict:
        """Convert a ToolDefinition to an Anthropic API tool dict."""
        return {
            "name": tool_def.name,
            "description": tool_def.description,
            "input_schema": tool_def.input_schema,
        }
