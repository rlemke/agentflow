"""Shared helpers for integration tests.

Provides compilation, workflow extraction, and execution helpers
that use real AFL source files and the full compiler pipeline.
"""

from pathlib import Path
from typing import Any

from afl.emitter import emit_dict
from afl.parser import AFLParser
from afl.runtime.agent_poller import AgentPoller
from afl.runtime.evaluator import Evaluator, ExecutionResult, ExecutionStatus
from afl.source import CompilerInput, FileOrigin, SourceEntry
from afl.validator import validate

# Paths
EXAMPLE_AFL_DIR = Path(__file__).parent.parent / "afl"
INTEGRATION_AFL_DIR = Path(__file__).parent / "afl"


def compile_afl_files(
    primary: str | Path,
    *libraries: str | Path,
) -> dict[str, Any]:
    """Compile AFL source files into a program dict.

    Args:
        primary: Path to the primary AFL source file
        *libraries: Paths to library AFL source files

    Returns:
        The full program dict (JSON-serializable AST)

    Raises:
        afl.parser.ParseError: On syntax errors
        ValueError: On validation errors
    """
    primary_path = Path(primary)
    primary_entry = SourceEntry(
        text=primary_path.read_text(),
        origin=FileOrigin(path=str(primary_path)),
    )

    lib_entries = []
    for lib in libraries:
        lib_path = Path(lib)
        lib_entries.append(
            SourceEntry(
                text=lib_path.read_text(),
                origin=FileOrigin(path=str(lib_path)),
                is_library=True,
            )
        )

    compiler_input = CompilerInput(
        primary_sources=[primary_entry],
        library_sources=lib_entries,
    )

    parser = AFLParser()
    program_ast, _registry = parser.parse_sources(compiler_input)

    result = validate(program_ast)
    if result.errors:
        messages = "; ".join(str(e) for e in result.errors)
        raise ValueError(f"Validation errors: {messages}")

    return emit_dict(program_ast, include_locations=False)


def extract_workflow(program_dict: dict, workflow_name: str) -> dict:
    """Find a WorkflowDecl by name in a compiled program dict.

    Searches recursively through namespaces and declarations.
    The emitted JSON uses both 'namespaces' (list of Namespace dicts)
    and 'workflows' (list of WorkflowDecl dicts) keys.

    Args:
        program_dict: The compiled program dict
        workflow_name: Name of the workflow to find

    Returns:
        The workflow dict

    Raises:
        KeyError: If the workflow is not found
    """

    def _search_node(node: dict) -> dict | None:
        # Check workflows list (emitter puts workflows here)
        for wf in node.get("workflows", []):
            if wf.get("name") == workflow_name:
                return wf
        # Check declarations list (alternative structure)
        for decl in node.get("declarations", []):
            if decl.get("type") == "WorkflowDecl" and decl.get("name") == workflow_name:
                return decl
            if decl.get("type") == "Namespace":
                found = _search_node(decl)
                if found:
                    return found
        # Recurse into namespaces list
        for ns in node.get("namespaces", []):
            found = _search_node(ns)
            if found:
                return found
        return None

    found = _search_node(program_dict)
    if found is None:
        raise KeyError(f"Workflow '{workflow_name}' not found in program")
    return found


def run_to_completion(
    evaluator: Evaluator,
    poller: AgentPoller,
    workflow_ast: dict,
    program_ast: dict,
    inputs: dict[str, Any] | None = None,
    max_rounds: int = 50,
) -> ExecutionResult:
    """Execute a workflow to completion through the AgentPoller pipeline.

    Loops: execute -> poll_once -> resume until COMPLETED, ERROR, or max_rounds.

    Args:
        evaluator: The Evaluator instance
        poller: AgentPoller with handlers registered
        workflow_ast: The workflow AST dict
        program_ast: The full program AST dict
        inputs: Workflow input parameters
        max_rounds: Maximum poll/resume cycles

    Returns:
        The final ExecutionResult
    """
    result = evaluator.execute(workflow_ast, inputs=inputs, program_ast=program_ast)

    if result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.ERROR):
        return result

    poller.cache_workflow_ast(result.workflow_id, workflow_ast)

    for _ in range(max_rounds):
        dispatched = poller.poll_once()

        if dispatched == 0:
            # No tasks claimed — try resuming anyway (may have been continued already)
            pass

        result = evaluator.resume(
            result.workflow_id, workflow_ast, program_ast, inputs
        )

        if result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.ERROR):
            return result

    return result
