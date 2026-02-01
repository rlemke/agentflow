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

"""Tests for in-memory persistence implementation."""

import pytest

from afl.runtime import (
    IterationChanges,
    MemoryStore,
    ObjectType,
    StepDefinition,
    block_id,
    workflow_id,
)


class TestMemoryStore:
    """Tests for MemoryStore persistence."""

    @pytest.fixture
    def store(self):
        """Create a fresh memory store."""
        return MemoryStore()

    @pytest.fixture
    def sample_step(self):
        """Create a sample step."""
        return StepDefinition.create(
            workflow_id=workflow_id(),
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            facet_name="TestFacet",
        )

    def test_save_and_get_step(self, store, sample_step):
        """Test saving and retrieving a step."""
        store.save_step(sample_step)

        retrieved = store.get_step(sample_step.id)
        assert retrieved is not None
        assert retrieved.id == sample_step.id
        assert retrieved.facet_name == "TestFacet"

    def test_get_returns_copy(self, store, sample_step):
        """Test that get returns a copy, not the original."""
        store.save_step(sample_step)

        retrieved = store.get_step(sample_step.id)
        retrieved.facet_name = "Modified"

        retrieved2 = store.get_step(sample_step.id)
        assert retrieved2.facet_name == "TestFacet"

    def test_get_nonexistent(self, store):
        """Test getting a nonexistent step."""
        result = store.get_step("nonexistent")
        assert result is None

    def test_steps_by_workflow(self, store):
        """Test getting steps by workflow."""
        wf_id = workflow_id()

        step1 = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        step2 = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        step3 = StepDefinition.create(
            workflow_id=workflow_id(),  # Different workflow
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )

        store.save_step(step1)
        store.save_step(step2)
        store.save_step(step3)

        steps = store.get_steps_by_workflow(wf_id)
        assert len(steps) == 2
        ids = {s.id for s in steps}
        assert step1.id in ids
        assert step2.id in ids

    def test_steps_by_block(self, store):
        """Test getting steps by block."""
        wf_id = workflow_id()
        b_id = block_id()

        step1 = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            block_id=b_id,
        )
        step2 = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            block_id=b_id,
        )
        step3 = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            block_id=block_id(),  # Different block
        )

        store.save_step(step1)
        store.save_step(step2)
        store.save_step(step3)

        steps = store.get_steps_by_block(b_id)
        assert len(steps) == 2

    def test_commit(self, store):
        """Test atomic commit."""
        changes = IterationChanges()

        step1 = StepDefinition.create(
            workflow_id=workflow_id(),
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )
        step2 = StepDefinition.create(
            workflow_id=workflow_id(),
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
        )

        changes.add_created_step(step1)
        changes.add_created_step(step2)

        store.commit(changes)

        assert store.step_count() == 2
        assert store.get_step(step1.id) is not None
        assert store.get_step(step2.id) is not None

    def test_step_exists(self, store):
        """Test idempotency check."""
        wf_id = workflow_id()
        b_id = block_id()

        step = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            statement_id="stmt-1",
            block_id=b_id,
        )
        store.save_step(step)

        assert store.step_exists("stmt-1", b_id) is True
        assert store.step_exists("stmt-2", b_id) is False
        assert store.step_exists("stmt-1", block_id()) is False

    def test_workflow_root(self, store):
        """Test getting workflow root."""
        wf_id = workflow_id()

        root = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.WORKFLOW,
        )
        child = StepDefinition.create(
            workflow_id=wf_id,
            object_type=ObjectType.VARIABLE_ASSIGNMENT,
            container_id=root.id,
            root_id=root.id,
        )

        store.save_step(root)
        store.save_step(child)

        retrieved = store.get_workflow_root(wf_id)
        assert retrieved is not None
        assert retrieved.id == root.id

    def test_clear(self, store, sample_step):
        """Test clearing the store."""
        store.save_step(sample_step)
        assert store.step_count() == 1

        store.clear()
        assert store.step_count() == 0
