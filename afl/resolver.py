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

"""Automatic dependency resolution for AFL sources.

Provides filesystem scanning and MongoDB-backed namespace lookup
to automatically discover and load missing namespace dependencies.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .ast import Program
from .source import CompilerInput, FileOrigin, SourceEntry, SourceRegistry

if TYPE_CHECKING:
    from .config import MongoDBConfig

logger = logging.getLogger(__name__)

_MAX_RESOLVE_ITERATIONS = 100


class NamespaceIndex:
    """Filesystem scanner that maps namespace names to AFL source files.

    Lazily scans directories for ``.afl`` files, parses each to extract
    namespace declarations, and builds a lookup table.
    """

    def __init__(self, search_paths: list[Path]) -> None:
        self._search_paths = search_paths
        self._index: dict[str, Path] | None = None

    def _build_index(self) -> dict[str, Path]:
        """Walk all search paths and parse ``.afl`` files for namespace names."""
        from .parser import AFLParser, ParseError

        index: dict[str, Path] = {}
        parser = AFLParser()

        seen_files: set[Path] = set()
        for search_dir in self._search_paths:
            if not search_dir.is_dir():
                logger.debug("Skipping non-directory search path: %s", search_dir)
                continue
            for afl_file in sorted(search_dir.glob("**/*.afl")):
                resolved = afl_file.resolve()
                if resolved in seen_files:
                    continue
                seen_files.add(resolved)
                try:
                    program = parser.parse(
                        afl_file.read_text(),
                        filename=str(afl_file),
                    )
                    for ns in program.namespaces:
                        if ns.name in index and index[ns.name] != resolved:
                            logger.warning(
                                "Duplicate namespace '%s' found in %s and %s",
                                ns.name,
                                index[ns.name],
                                resolved,
                            )
                        index[ns.name] = resolved
                except ParseError as e:
                    logger.debug("Skipping unparseable file %s: %s", afl_file, e)
        return index

    def find_namespace(self, name: str) -> Path | None:
        """Find the file that defines the given namespace.

        Returns:
            Path to the ``.afl`` file, or ``None`` if not found.
        """
        if self._index is None:
            self._index = self._build_index()
        return self._index.get(name)

    def all_namespaces(self) -> dict[str, Path]:
        """Return the full namespace → path mapping."""
        if self._index is None:
            self._index = self._build_index()
        return dict(self._index)


class MongoDBNamespaceResolver:
    """Resolves namespace names to source text via MongoDB ``afl_sources`` collection."""

    def __init__(self, config: MongoDBConfig) -> None:
        self._config = config
        self._store: object | None = None

    def _get_store(self) -> object:
        """Lazily create MongoStore."""
        if self._store is None:
            from .runtime.mongo_store import MongoStore

            self._store = MongoStore.from_config(self._config, create_indexes=False)
        return self._store

    def find_namespace(self, name: str) -> str | None:
        """Look up a namespace in MongoDB.

        Returns:
            Source text if found, or ``None``.
        """
        try:
            store = self._get_store()
            source = store.get_source_by_namespace(name)  # type: ignore[union-attr]
            return source.source_text if source else None
        except Exception as e:
            logger.debug("MongoDB namespace lookup failed for '%s': %s", name, e)
            return None

    def batch_find(self, names: set[str]) -> dict[str, str]:
        """Batch-fetch multiple namespaces from MongoDB.

        Returns:
            Dict mapping namespace_name → source_text for found namespaces.
        """
        if not names:
            return {}
        try:
            store = self._get_store()
            sources = store.get_sources_by_namespaces(names)  # type: ignore[union-attr]
            return {name: ps.source_text for name, ps in sources.items()}
        except Exception as e:
            logger.debug("MongoDB batch namespace lookup failed: %s", e)
            return {}


class DependencyResolver:
    """Iterative fixpoint resolver for AFL namespace dependencies.

    Given a parsed ``Program``, finds missing namespaces (referenced
    via ``use`` statements but not yet defined), loads them from the
    filesystem or MongoDB, parses them, and merges into the program.
    Repeats until no new namespaces are discovered.
    """

    def __init__(
        self,
        filesystem_index: NamespaceIndex | None = None,
        mongodb_resolver: MongoDBNamespaceResolver | None = None,
    ) -> None:
        self._fs_index = filesystem_index
        self._mongo_resolver = mongodb_resolver
        self._loaded_sources: set[str] = set()

    def resolve(
        self,
        program: Program,
        registry: SourceRegistry,
        compiler_input: CompilerInput,
    ) -> tuple[Program, SourceRegistry, CompilerInput]:
        """Resolve all missing namespace dependencies.

        Returns:
            Updated (program, registry, compiler_input) tuple with
            all discovered dependencies merged in.
        """
        from .parser import AFLParser, ParseError

        parser = AFLParser()

        for iteration in range(_MAX_RESOLVE_ITERATIONS):
            defined = {ns.name for ns in program.namespaces}
            needed: set[str] = set()
            for ns in program.namespaces:
                for use in ns.uses:
                    needed.add(use.name)

            missing = needed - defined
            if not missing:
                logger.debug("Dependency resolution complete after %d iteration(s)", iteration + 1)
                return program, registry, compiler_input

            logger.debug("Iteration %d: missing namespaces: %s", iteration + 1, missing)

            new_programs: list[Program] = []
            resolved_any = False

            # Try filesystem first
            if self._fs_index is not None:
                for name in list(missing):
                    file_path = self._fs_index.find_namespace(name)
                    if file_path is None:
                        continue
                    source_key = f"file://{file_path.resolve()}"
                    if source_key in self._loaded_sources:
                        continue
                    self._loaded_sources.add(source_key)

                    try:
                        text = file_path.read_text()
                        entry = SourceEntry(
                            text=text,
                            origin=FileOrigin(path=str(file_path)),
                            is_library=True,
                        )
                        compiler_input.library_sources.append(entry)
                        registry.register_entry(entry)

                        sub_program = parser.parse(
                            text,
                            filename=str(file_path),
                            source_id=entry.source_id,
                        )
                        new_programs.append(sub_program)
                        resolved_any = True
                        logger.debug("Resolved '%s' from filesystem: %s", name, file_path)
                    except (ParseError, OSError) as e:
                        logger.warning("Failed to load '%s' from %s: %s", name, file_path, e)

            # Then try MongoDB for still-missing namespaces
            if self._mongo_resolver is not None:
                # Recalculate what's still missing after filesystem resolution
                newly_defined = {
                    ns.name for p in new_programs for ns in p.namespaces
                }
                still_missing = missing - newly_defined - defined
                if still_missing:
                    mongo_results = self._mongo_resolver.batch_find(still_missing)
                    for name, source_text in mongo_results.items():
                        source_key = f"mongodb://{name}"
                        if source_key in self._loaded_sources:
                            continue
                        self._loaded_sources.add(source_key)

                        try:
                            from .source import MongoDBOrigin

                            entry = SourceEntry(
                                text=source_text,
                                origin=MongoDBOrigin(
                                    collection_id=name,
                                    display_name=name,
                                ),
                                is_library=True,
                            )
                            compiler_input.library_sources.append(entry)
                            registry.register_entry(entry)

                            sub_program = parser.parse(
                                source_text,
                                filename=f"mongodb://{name}",
                                source_id=entry.source_id,
                            )
                            new_programs.append(sub_program)
                            resolved_any = True
                            logger.debug("Resolved '%s' from MongoDB", name)
                        except (ParseError, Exception) as e:
                            logger.warning(
                                "Failed to parse MongoDB source for '%s': %s", name, e
                            )

            if not resolved_any:
                logger.debug(
                    "No new namespaces resolved; remaining missing: %s",
                    missing - {ns.name for p in new_programs for ns in p.namespaces},
                )
                return program, registry, compiler_input

            # Merge new programs into the main program
            for p in new_programs:
                program.namespaces.extend(p.namespaces)
                program.facets.extend(p.facets)
                program.event_facets.extend(p.event_facets)
                program.workflows.extend(p.workflows)
                program.implicits.extend(p.implicits)
                program.schemas.extend(p.schemas)

        logger.warning("Dependency resolution hit max iterations (%d)", _MAX_RESOLVE_ITERATIONS)
        return program, registry, compiler_input
