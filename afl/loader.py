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

"""AFL source loaders for different origin types.

Provides loading functionality for:
- File system sources
- MongoDB sources (stub)
- Maven artifacts (stub)
"""

from pathlib import Path

from .source import (
    FileOrigin,
    SourceEntry,
)


class SourceLoader:
    """Loads AFL source from various origins."""

    @staticmethod
    def load_file(path: str | Path, is_library: bool = False) -> SourceEntry:
        """Load source from a file.

        Args:
            path: Path to the AFL source file
            is_library: Whether this is a library source

        Returns:
            SourceEntry with file content and provenance

        Raises:
            FileNotFoundError: If the file doesn't exist
            IOError: If the file can't be read
        """
        file_path = Path(path)
        text = file_path.read_text()
        return SourceEntry(
            text=text,
            origin=FileOrigin(path=str(file_path)),
            is_library=is_library,
        )

    @staticmethod
    def load_mongodb(
        collection_id: str,
        display_name: str,
        is_library: bool = True,
    ) -> SourceEntry:
        """Load source from MongoDB.

        Args:
            collection_id: MongoDB document ID
            display_name: Human-readable name
            is_library: Whether this is a library source

        Returns:
            SourceEntry with content and provenance

        Raises:
            NotImplementedError: MongoDB loader not yet implemented
        """
        raise NotImplementedError(
            "MongoDB loader not yet implemented. "
            f"Would load document '{collection_id}' ({display_name})"
        )

    @staticmethod
    def load_maven(
        group_id: str,
        artifact_id: str,
        version: str,
        classifier: str = "",
        is_library: bool = True,
    ) -> SourceEntry:
        """Load source from Maven repository.

        Args:
            group_id: Maven group ID (e.g., "com.example")
            artifact_id: Maven artifact ID (e.g., "my-lib")
            version: Maven version (e.g., "1.0.0")
            classifier: Optional classifier (e.g., "sources")
            is_library: Whether this is a library source

        Returns:
            SourceEntry with content and provenance

        Raises:
            NotImplementedError: Maven loader not yet implemented
        """
        coords = f"{group_id}:{artifact_id}:{version}"
        if classifier:
            coords += f":{classifier}"
        raise NotImplementedError(
            f"Maven loader not yet implemented. Would load artifact '{coords}'"
        )
