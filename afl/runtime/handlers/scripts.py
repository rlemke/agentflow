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

"""Script phase handlers.

Handles facet and statement script execution phases.
In the current implementation, these are pass-through states.
"""

from typing import TYPE_CHECKING

from ..changers.base import StateChangeResult
from .base import StateHandler

if TYPE_CHECKING:
    pass


class FacetScriptsBeginHandler(StateHandler):
    """Handler for state.facet.scripts.Begin.

    Executes facet-level scripts. Currently a pass-through.
    """

    def process_state(self) -> StateChangeResult:
        """Begin facet scripts execution."""
        # Currently no facet scripts to execute
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)


class FacetScriptsEndHandler(StateHandler):
    """Handler for state.facet.scripts.End.

    Completes facet scripts phase.
    """

    def process_state(self) -> StateChangeResult:
        """End facet scripts execution."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)


class StatementScriptsBeginHandler(StateHandler):
    """Handler for state.statement.scripts.Begin.

    Executes statement-level scripts. Currently a pass-through.
    """

    def process_state(self) -> StateChangeResult:
        """Begin statement scripts execution."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)


class StatementScriptsEndHandler(StateHandler):
    """Handler for state.statement.scripts.End.

    Completes statement scripts phase.
    """

    def process_state(self) -> StateChangeResult:
        """End statement scripts execution."""
        self.step.request_state_change(True)
        return StateChangeResult(step=self.step)
