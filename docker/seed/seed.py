#!/usr/bin/env python3
"""
Seed script - Populates MongoDB with example workflows.

This script:
1. Parses example AFL files
2. Stores compiled workflows in the flows collection
3. Creates sample tasks that can be executed by the runner

Run with: docker compose run seed
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime

# Add parent to path for afl imports
sys.path.insert(0, "/app")

from pymongo import MongoClient

from afl.parser import parse
from afl.emitter import emit_dict
from afl.validator import validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed")

# Example AFL sources to seed
EXAMPLE_SOURCES = {
    "addone-example": '''
// Simple AddOne workflow for testing
namespace handlers {
    event facet AddOne(value: Long) => (result: Long)
    event facet Multiply(a: Long, b: Long) => (result: Long)
    event facet Greet(name: String) => (message: String)

    workflow AddOneWorkflow(input: Long) => (output: Long) andThen {
        added = AddOne(value = $.input)
        yield AddOneWorkflow(output = added.result)
    }

    workflow DoubleAddOne(input: Long) => (output: Long) andThen {
        first = AddOne(value = $.input)
        second = AddOne(value = first.result)
        yield DoubleAddOne(output = second.result)
    }

    workflow MultiplyAndAdd(a: Long, b: Long) => (result: Long) andThen {
        product = Multiply(a = $.a, b = $.b)
        incremented = AddOne(value = product.result)
        yield MultiplyAndAdd(result = incremented.result)
    }

    workflow GreetAndCount(name: String) => (greeting: String, count: Long) andThen {
        hello = Greet(name = $.name)
        one = AddOne(value = 0)
        yield GreetAndCount(greeting = hello.message, count = one.result)
    }
}
''',
    "chain-example": '''
// Chain workflow - multiple steps in sequence
namespace chain {
    use handlers

    workflow ChainOfThree(start: Long) => (final: Long) andThen {
        step1 = AddOne(value = $.start)
        step2 = AddOne(value = step1.result)
        step3 = AddOne(value = step2.result)
        yield ChainOfThree(final = step3.result)
    }
}
''',
}


def seed_database():
    """Seed the database with example workflows."""
    mongodb_url = os.environ.get("AFL_MONGODB_URL", "mongodb://localhost:27017")
    database = os.environ.get("AFL_MONGODB_DATABASE", "afl")

    logger.info(f"Connecting to {mongodb_url}/{database}")
    client = MongoClient(mongodb_url)
    db = client[database]

    # Collections
    flows_col = db["flows"]
    workflows_col = db["workflows"]
    runners_col = db["runners"]
    tasks_col = db["tasks"]

    # Clear existing seed data (optional - comment out to preserve)
    # logger.info("Clearing existing seed data...")
    # flows_col.delete_many({"name": {"$regex": "^seed-"}})

    seeded_count = 0

    for name, source in EXAMPLE_SOURCES.items():
        logger.info(f"Processing: {name}")

        # Parse and validate
        try:
            ast = parse(source, filename=f"{name}.afl")
            result = validate(ast)

            if not result.is_valid:
                logger.error(f"  Validation failed: {result.errors}")
                continue

            # Emit to dict
            compiled = emit_dict(ast)

        except Exception as e:
            logger.error(f"  Parse error: {e}")
            continue

        # Create flow document
        flow_id = str(uuid.uuid4())
        flow_doc = {
            "uuid": flow_id,
            "name": f"seed-{name}",
            "path": f"/seed/{name}.afl",
            "sources": [
                {
                    "name": f"{name}.afl",
                    "content": source,
                    "language": "afl",
                }
            ],
            "compiled": compiled,
            "created": datetime.utcnow().isoformat(),
            "seeded": True,
        }

        # Extract workflow names
        workflow_names = []
        for ns in compiled.get("namespaces", []):
            for wf in ns.get("workflows", []):
                workflow_names.append(f"{ns['name']}.{wf['name']}")
        for wf in compiled.get("workflows", []):
            workflow_names.append(wf["name"])

        flow_doc["workflows"] = workflow_names

        # Upsert flow
        flows_col.update_one(
            {"name": flow_doc["name"]},
            {"$set": flow_doc},
            upsert=True
        )
        logger.info(f"  Stored flow: {flow_doc['name']} ({len(workflow_names)} workflows)")
        seeded_count += 1

    logger.info(f"Seeded {seeded_count} example flows")

    # Create a sample ready-to-run task
    logger.info("Creating sample executable task...")

    # Find the addone flow
    addone_flow = flows_col.find_one({"name": "seed-addone-example"})
    if addone_flow:
        task_id = str(uuid.uuid4())
        task_doc = {
            "uuid": task_id,
            "name": "afl:execute",
            "flow_id": addone_flow["uuid"],
            "workflow_id": "",
            "workflow_name": "handlers.AddOneWorkflow",
            "runner_id": "",
            "step_id": "",
            "state": "pending",
            "created": datetime.utcnow().isoformat(),
            "updated": datetime.utcnow().isoformat(),
            "data": {
                "inputs": {"input": 41},
            },
            "data_type": "execute",
            "task_list_name": "afl:execute",
            "seeded": True,
        }

        tasks_col.update_one(
            {"uuid": task_id},
            {"$set": task_doc},
            upsert=True
        )
        logger.info(f"  Created task: AddOneWorkflow(input=41) -> expecting output=42")

    # Show summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Seed Complete!")
    logger.info("=" * 60)
    logger.info(f"Flows: {flows_col.count_documents({})}")
    logger.info(f"Tasks: {tasks_col.count_documents({})}")
    logger.info("")
    logger.info("View the dashboard at: http://localhost:8080")
    logger.info("=" * 60)


if __name__ == "__main__":
    seed_database()
