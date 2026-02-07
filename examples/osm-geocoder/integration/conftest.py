"""Shared fixtures for integration tests.

All tests in this directory require a running MongoDB instance.
Run with: pytest examples/osm-geocoder/integration/ -v --mongodb
"""

import pytest

from afl.runtime import Evaluator, Telemetry
from afl.runtime.agent_poller import AgentPoller, AgentPollerConfig


def _use_real_mongodb(request) -> bool:
    """Check if --mongodb flag was passed."""
    return request.config.getoption("--mongodb", default=False)


# Skip entire directory if --mongodb not passed
def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --mongodb is provided."""
    if not config.getoption("--mongodb", default=False):
        skip = pytest.mark.skip(reason="Integration tests require --mongodb flag")
        for item in items:
            item.add_marker(skip)


@pytest.fixture
def mongo_store(request):
    """Create a MongoStore backed by a real MongoDB server.

    Uses AFL config for connection settings. Database is dropped after each test.
    """
    from afl.config import load_config
    from afl.runtime.mongo_store import MongoStore

    config = load_config()
    store = MongoStore(
        connection_string=config.mongodb.connection_string(),
        database_name="afl_integration_test",
    )
    yield store
    store.drop_database()
    store.close()


@pytest.fixture
def evaluator(mongo_store):
    """Create an Evaluator backed by MongoDB."""
    return Evaluator(persistence=mongo_store, telemetry=Telemetry(enabled=False))


@pytest.fixture
def poller(mongo_store, evaluator):
    """Create an AgentPoller with no handlers registered.

    Tests should register their own handlers before use.
    """
    return AgentPoller(
        persistence=mongo_store,
        evaluator=evaluator,
        config=AgentPollerConfig(service_name="integration-test"),
    )
