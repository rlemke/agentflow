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

"""Tests for Jinja2 template filters."""

from afl.dashboard.filters import (
    duration_fmt,
    state_color,
    state_label,
    timestamp_fmt,
    truncate_uuid,
)


class TestTimestampFmt:
    def test_zero_returns_dash(self):
        assert timestamp_fmt(0) == "—"

    def test_none_returns_dash(self):
        assert timestamp_fmt(None) == "—"

    def test_valid_timestamp(self):
        # 2024-01-01 00:00:00 UTC = 1704067200000 ms
        result = timestamp_fmt(1704067200000)
        assert "2024" in result
        assert "01" in result

    def test_custom_format(self):
        result = timestamp_fmt(1704067200000, fmt="%Y")
        assert result == "2024"


class TestDurationFmt:
    def test_zero_returns_dash(self):
        assert duration_fmt(0) == "—"

    def test_none_returns_dash(self):
        assert duration_fmt(None) == "—"

    def test_seconds(self):
        assert duration_fmt(5000) == "5s"

    def test_minutes(self):
        assert duration_fmt(90000) == "1m 30s"

    def test_hours(self):
        assert duration_fmt(3_660_000) == "1h 1m"


class TestStateColor:
    def test_running(self):
        assert state_color("running") == "primary"

    def test_completed(self):
        assert state_color("completed") == "success"

    def test_failed(self):
        assert state_color("failed") == "danger"

    def test_paused(self):
        assert state_color("paused") == "warning"

    def test_none(self):
        assert state_color(None) == "secondary"

    def test_unknown(self):
        assert state_color("some_weird_state") == "secondary"

    def test_dotted_state(self):
        # Extracts last segment
        assert state_color("state.facet.completion.Complete") == "secondary"


class TestStateLabel:
    def test_simple(self):
        assert state_label("running") == "running"

    def test_dotted(self):
        assert state_label("state.facet.initialization.Begin") == "Begin"

    def test_none(self):
        assert state_label(None) == "unknown"


class TestTruncateUuid:
    def test_truncate(self):
        assert truncate_uuid("abcdef12-3456-7890") == "abcdef12"

    def test_custom_length(self):
        assert truncate_uuid("abcdef12-3456-7890", length=4) == "abcd"

    def test_none(self):
        assert truncate_uuid(None) == "—"
