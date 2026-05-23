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

"""Claude workflow catalog — store, version, and run LLM-authored FFL workflows.

A *catalog entry* (``CatalogEntry``, collection ``claude_workflows``) is the
stable, human/LLM-facing index for one logical workflow or library: a slug,
description, tags, and the parameter schema. Each entry has one or more
immutable *revisions* (``CatalogRevision``, collection
``claude_workflow_revisions``): a frozen, content-hashed snapshot of the FFL
plus the runnable ``FlowDefinition`` it materialized. Runs pin a revision, so
re-running with different inputs always re-uses the identical workflow body —
edits create a new version rather than mutating the old one.

See ``CatalogService`` for the operations (save / search / get / publish / run)
and ``docs/architecture/claude-workflow-catalog.md`` for the design.
"""

from .entities import CatalogEntry, CatalogRevision
from .service import CatalogError, CatalogRunBlocked, CatalogService, SaveResult
from .store import CatalogStore, InMemoryCatalogStore, MongoCatalogStore

__all__ = [
    "CatalogEntry",
    "CatalogRevision",
    "CatalogService",
    "CatalogError",
    "CatalogRunBlocked",
    "SaveResult",
    "CatalogStore",
    "InMemoryCatalogStore",
    "MongoCatalogStore",
]
