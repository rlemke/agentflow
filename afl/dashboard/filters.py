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

"""Jinja2 template filters for the dashboard."""

from __future__ import annotations

import datetime

from jinja2 import Environment


def timestamp_fmt(value: int | float | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a millisecond-epoch timestamp as a human-readable string."""
    if not value:
        return "—"
    dt = datetime.datetime.fromtimestamp(value / 1000, tz=datetime.UTC)
    return dt.strftime(fmt)


def duration_fmt(ms: int | float | None) -> str:
    """Format a duration in milliseconds as a compact string."""
    if not ms:
        return "—"
    seconds = int(ms) // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


_STATE_COLORS: dict[str, str] = {
    # Runner states
    "created": "secondary",
    "running": "primary",
    "completed": "success",
    "failed": "danger",
    "paused": "warning",
    "cancelled": "secondary",
    # Server states
    "startup": "secondary",
    "shutdown": "secondary",
    "error": "danger",
    # Task states
    "pending": "warning",
    "ignored": "secondary",
    "canceled": "secondary",
}


def state_color(state: str | None) -> str:
    """Return a CSS colour class for the given state string."""
    if not state:
        return "secondary"
    key = state.lower().rsplit(".", 1)[-1] if "." in (state or "") else (state or "").lower()
    return _STATE_COLORS.get(key, "secondary")


def state_label(state: str | None) -> str:
    """Extract a short label from a dotted state string."""
    if not state:
        return "unknown"
    return state.rsplit(".", 1)[-1]


def truncate_uuid(value: str | None, length: int = 8) -> str:
    """Truncate a UUID for display."""
    if not value:
        return "—"
    return value[:length]


def register_filters(env: Environment) -> None:
    """Register all custom filters on a Jinja2 environment."""
    env.filters["timestamp"] = timestamp_fmt
    env.filters["duration"] = duration_fmt
    env.filters["state_color"] = state_color
    env.filters["state_label"] = state_label
    env.filters["truncate_uuid"] = truncate_uuid
