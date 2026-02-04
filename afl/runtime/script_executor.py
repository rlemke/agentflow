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

"""Script execution for AFL script blocks.

Provides sandboxed execution of Python scripts defined in facet script blocks.
Scripts receive input via `params` dict and return output via `result` dict.

Example usage::

    executor = ScriptExecutor()
    result = executor.execute(
        code='result["output"] = params["input"].upper()',
        params={"input": "hello"},
    )
    # result == {"output": "HELLO"}

Security Note:
    The default executor uses a restricted global namespace that excludes
    dangerous builtins. For production use with untrusted code, consider
    using RestrictedPython or a sandboxed subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ScriptError(Exception):
    """Error raised during script execution."""

    def __init__(self, message: str, original: Exception | None = None):
        super().__init__(message)
        self.original = original


@dataclass
class ScriptResult:
    """Result of script execution."""

    success: bool
    result: dict[str, Any]
    error: str | None = None


# Allowed builtins for sandboxed execution
_SAFE_BUILTINS = {
    # Types
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "frozenset": frozenset,
    "bytes": bytes,
    "bytearray": bytearray,
    # Functions
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "all": all,
    "any": any,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "hasattr": hasattr,
    "getattr": getattr,
    "setattr": setattr,
    "type": type,
    "repr": repr,
    "print": print,  # Captured output could be logged
    # None, True, False
    "None": None,
    "True": True,
    "False": False,
    # Exceptions (for catching)
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "AttributeError": AttributeError,
}


class ScriptExecutor:
    """Executes Python scripts in a sandboxed environment.

    Scripts have access to:
    - `params`: Input parameters (read-only dict)
    - `result`: Output dict (should be populated by the script)
    - Safe builtins (no __import__, exec, eval, open, etc.)

    Attributes:
        timeout: Execution timeout in seconds (not enforced in basic mode)
    """

    def __init__(self, timeout: float = 30.0):
        """Initialize the executor.

        Args:
            timeout: Maximum execution time in seconds (informational only
                     in basic mode; use with subprocess for enforcement)
        """
        self.timeout = timeout

    def execute(
        self,
        code: str,
        params: dict[str, Any] | None = None,
        language: str = "python",
    ) -> ScriptResult:
        """Execute a script with the given parameters.

        Args:
            code: The script source code
            params: Input parameters (available as `params` in script)
            language: Script language (only "python" supported)

        Returns:
            ScriptResult with success status and result dict

        Raises:
            ScriptError: If language is not supported
        """
        if language != "python":
            return ScriptResult(
                success=False,
                result={},
                error=f"Unsupported script language: {language}",
            )

        return self._execute_python(code, params or {})

    def _execute_python(
        self,
        code: str,
        params: dict[str, Any],
    ) -> ScriptResult:
        """Execute Python code in a sandboxed environment.

        Args:
            code: Python source code
            params: Input parameters

        Returns:
            ScriptResult with execution outcome
        """
        # Prepare sandboxed globals
        result: dict[str, Any] = {}
        sandbox_globals = {
            "__builtins__": _SAFE_BUILTINS,
            "params": dict(params),  # Copy to prevent modification
            "result": result,
        }

        try:
            # Compile to check for syntax errors
            compiled = compile(code, "<script>", "exec")

            # Execute in sandboxed namespace
            exec(compiled, sandbox_globals)

            return ScriptResult(success=True, result=result)

        except SyntaxError as e:
            return ScriptResult(
                success=False,
                result={},
                error=f"Syntax error in script: {e}",
            )
        except Exception as e:
            return ScriptResult(
                success=False,
                result={},
                error=f"Script execution error: {type(e).__name__}: {e}",
            )


def execute_script(
    code: str,
    params: dict[str, Any] | None = None,
    language: str = "python",
) -> dict[str, Any]:
    """Convenience function to execute a script and return results.

    Args:
        code: The script source code
        params: Input parameters
        language: Script language

    Returns:
        Result dict from script execution

    Raises:
        ScriptError: If script execution fails
    """
    executor = ScriptExecutor()
    result = executor.execute(code, params, language)

    if not result.success:
        raise ScriptError(result.error or "Unknown error")

    return result.result
