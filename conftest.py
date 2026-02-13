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

"""Root pytest configuration for AFL tests."""


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--mongodb",
        action="store_true",
        default=False,
        help="Run MongoDB tests against a real server (uses AFL config for connection)",
    )
    parser.addoption(
        "--hdfs",
        action="store_true",
        default=False,
        help="Run HDFS integration tests against live containers (namenode on localhost:8020)",
    )
