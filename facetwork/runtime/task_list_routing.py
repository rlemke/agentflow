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

"""Workflow name → task list routing.

Used by submission and completion paths to decide which task list a
workflow's tasks should land on. Configured via the
``AFL_WORKFLOW_TASK_LIST_MAP`` environment variable using comma-separated
``prefix=list`` pairs::

    AFL_WORKFLOW_TASK_LIST_MAP=osm.=osm,anthropic.=anthropic,noaa.=weather

Longest-prefix match wins; the empty prefix ``=foo`` sets the global
fallback (otherwise ``"default"``).

.. note::
   Callers must pass the **fully qualified** workflow name (e.g.
   ``"osm.UnitedStates.analysis.AnalyzeRegion"``), not the short name.
   ``ast_utils.find_workflow()`` returns the inner ``WorkflowDecl`` dict
   whose ``"name"`` field is only the *unqualified* tail (``"AnalyzeRegion"``)
   — the namespace prefix lives on the enclosing ``Namespace`` decl and is
   stripped during lookup. Passing the short name here silently falls back
   to ``"default"`` because no prefix can match it.

   ``ExecutionContext.qualified_workflow_name`` carries the correct value
   end-to-end; submission sites pass the workflow name they were given
   (which is already qualified).
"""

from __future__ import annotations

import logging
import os

DEFAULT_TASK_LIST = "default"
ENV_VAR = "AFL_WORKFLOW_TASK_LIST_MAP"

logger = logging.getLogger(__name__)


def parse_map(spec: str) -> list[tuple[str, str]]:
    """Parse a ``prefix=list,prefix=list`` spec into sorted-longest-first pairs.

    Empty or malformed entries are skipped with a warning. Returns a list of
    ``(prefix, task_list)`` tuples sorted by descending prefix length so the
    first match in iteration order is the longest-prefix match.
    """
    pairs: list[tuple[str, str]] = []
    for raw in spec.split(","):
        entry = raw.strip()
        if not entry:
            continue
        if "=" not in entry:
            logger.warning("%s: ignoring malformed entry %r (no '=')", ENV_VAR, entry)
            continue
        prefix, _, task_list = entry.partition("=")
        prefix = prefix.strip()
        task_list = task_list.strip()
        if not task_list:
            logger.warning("%s: ignoring entry %r (empty task list)", ENV_VAR, entry)
            continue
        pairs.append((prefix, task_list))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _load_map() -> list[tuple[str, str]]:
    spec = os.environ.get(ENV_VAR, "")
    return parse_map(spec) if spec else []


def resolve_task_list(workflow_name: str, *, default: str = DEFAULT_TASK_LIST) -> str:
    """Resolve the task list for a workflow by longest-prefix match.

    Args:
        workflow_name: Fully-qualified workflow name (e.g. ``osm.AnalyzeRegion``).
        default: Fallback when no prefix matches and no empty-prefix entry is set.

    Returns:
        The configured task list, or ``default`` if no entry matches.
    """
    name = workflow_name or ""
    for prefix, task_list in _load_map():
        if name.startswith(prefix):
            return task_list
    return default
