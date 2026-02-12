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

"""AFL configuration management.

Provides configuration dataclasses for external service connections
and a loader that reads from config files or environment variables.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MongoDBConfig:
    """MongoDB connection configuration.

    Attributes:
        url: MongoDB connection URL
        username: Authentication username
        password: Authentication password
        auth_source: Authentication database name
        database: Target database name (e.g. "afl", "afl_test", "afl_dev_alice")
    """

    url: str = "mongodb://localhost:27017"
    username: str = ""
    password: str = ""
    auth_source: str = "admin"
    database: str = "afl"

    def connection_string(self) -> str:
        """Build the effective connection string.

        If username/password differ from those embedded in the URL,
        the explicit username/password and auth_source are used to
        construct a new connection string.

        Returns:
            A MongoDB connection URI.
        """
        return self.url

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MongoDBConfig:
        """Create from a dictionary.

        Keys may use either snake_case (``auth_source``) or
        camelCase (``authSource``).
        """
        return cls(
            url=data.get("url", cls.url),
            username=data.get("username", cls.username),
            password=data.get("password", cls.password),
            auth_source=data.get("auth_source", data.get("authSource", cls.auth_source)),
            database=data.get("database", cls.database),
        )

    @classmethod
    def from_env(cls) -> MongoDBConfig:
        """Create from environment variables.

        Recognised variables (all optional – defaults apply for missing vars):
            AFL_MONGODB_URL
            AFL_MONGODB_USERNAME
            AFL_MONGODB_PASSWORD
            AFL_MONGODB_AUTH_SOURCE
            AFL_MONGODB_DATABASE
        """
        defaults = cls()
        return cls(
            url=os.environ.get("AFL_MONGODB_URL", defaults.url),
            username=os.environ.get("AFL_MONGODB_USERNAME", defaults.username),
            password=os.environ.get("AFL_MONGODB_PASSWORD", defaults.password),
            auth_source=os.environ.get("AFL_MONGODB_AUTH_SOURCE", defaults.auth_source),
            database=os.environ.get("AFL_MONGODB_DATABASE", defaults.database),
        )


@dataclass
class ResolverConfig:
    """Dependency resolver configuration.

    Attributes:
        source_paths: Additional directories to scan for AFL sources
        auto_resolve: Enable automatic dependency resolution
        mongodb_resolve: Enable MongoDB namespace lookup during resolution
    """

    source_paths: list[str] = field(default_factory=list)
    auto_resolve: bool = False
    mongodb_resolve: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolverConfig:
        """Create from a dictionary."""
        return cls(
            source_paths=data.get("source_paths", []),
            auto_resolve=data.get("auto_resolve", False),
            mongodb_resolve=data.get("mongodb_resolve", False),
        )

    @classmethod
    def from_env(cls) -> ResolverConfig:
        """Create from environment variables.

        Recognised variables (all optional):
            AFL_RESOLVER_SOURCE_PATHS  (colon-separated list of paths)
            AFL_RESOLVER_AUTO_RESOLVE  ("true"/"1" to enable)
            AFL_RESOLVER_MONGODB_RESOLVE  ("true"/"1" to enable)
        """
        paths_str = os.environ.get("AFL_RESOLVER_SOURCE_PATHS", "")
        source_paths = [p for p in paths_str.split(":") if p] if paths_str else []
        auto_resolve = os.environ.get("AFL_RESOLVER_AUTO_RESOLVE", "").lower() in ("true", "1")
        mongodb_resolve = os.environ.get("AFL_RESOLVER_MONGODB_RESOLVE", "").lower() in (
            "true",
            "1",
        )
        return cls(
            source_paths=source_paths,
            auto_resolve=auto_resolve,
            mongodb_resolve=mongodb_resolve,
        )


@dataclass
class AFLConfig:
    """Top-level AFL configuration.

    Attributes:
        mongodb: MongoDB connection settings
        resolver: Dependency resolver settings
    """

    mongodb: MongoDBConfig = field(default_factory=MongoDBConfig)
    resolver: ResolverConfig = field(default_factory=ResolverConfig)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "mongodb": self.mongodb.to_dict(),
            "resolver": self.resolver.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AFLConfig:
        """Create from a dictionary (e.g. parsed JSON)."""
        mongodb_data = data.get("mongodb", {})
        resolver_data = data.get("resolver", {})
        return cls(
            mongodb=MongoDBConfig.from_dict(mongodb_data),
            resolver=ResolverConfig.from_dict(resolver_data),
        )

    @classmethod
    def from_env(cls) -> AFLConfig:
        """Create from environment variables."""
        return cls(
            mongodb=MongoDBConfig.from_env(),
            resolver=ResolverConfig.from_env(),
        )


# -- Config file loading -----------------------------------------------------

DEFAULT_CONFIG_FILENAME = "afl.config.json"

_SEARCH_PATHS = [
    Path.cwd,  # current directory
    lambda: Path.home() / ".afl",  # user home
    lambda: Path("/etc/afl"),  # system-wide
]


def _find_config_file(filename: str = DEFAULT_CONFIG_FILENAME) -> Path | None:
    """Search well-known locations for a config file.

    Search order:
        1. ``$AFL_CONFIG`` environment variable (explicit path)
        2. Current working directory
        3. ``~/.afl/``
        4. ``/etc/afl/``

    Returns:
        Path to the first config file found, or ``None``.
    """
    explicit = os.environ.get("AFL_CONFIG")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        return None

    for path_fn in _SEARCH_PATHS:
        candidate = path_fn() / filename
        if candidate.is_file():
            return candidate
    return None


def load_config(path: str | Path | None = None) -> AFLConfig:
    """Load AFL configuration.

    Resolution order:
        1. Explicit *path* argument
        2. Config file found via :func:`_find_config_file`
        3. Environment variables (``AFL_MONGODB_*``)
        4. Built-in defaults

    Args:
        path: Optional explicit path to a JSON config file.

    Returns:
        Populated :class:`AFLConfig` instance.
    """
    config_path: Path | None = Path(path) if path else _find_config_file()

    if config_path and config_path.is_file():
        text = config_path.read_text()
        data = json.loads(text)
        return AFLConfig.from_dict(data)

    # Fall back to env vars / defaults
    return AFLConfig.from_env()
