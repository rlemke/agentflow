#!/usr/bin/env python3
"""
Seed script - Populates MongoDB with example workflows.

This script:
1. Seeds inline example workflows (addone, chain, parallel)
2. Discovers and seeds AFL files from examples/ directories
3. Creates proper FlowDefinition + WorkflowDefinition entities
   so the Dashboard "Run" button works

Run with: docker compose --profile seed run --rm seed
"""

import glob
import json
import logging
import os
import sys
import time

# Add parent to path for afl imports
sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed")

SEED_PATH = "docker:seed"

# Inline example AFL sources
INLINE_SOURCES = {
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
        step1 = handlers.AddOne(value = $.start)
        step2 = handlers.AddOne(value = step1.result)
        step3 = handlers.AddOne(value = step2.result)
        yield ChainOfThree(final = step3.result)
    }
}
''',
    "parallel-example": '''
// Parallel workflow - demonstrates concurrent step execution
namespace parallel {
    use handlers

    // Two independent AddOne calls can execute in parallel
    workflow ParallelAdd(a: Long, b: Long) => (sumPlusTwo: Long) andThen {
        // These two steps have no dependencies on each other
        addedA = handlers.AddOne(value = $.a)
        addedB = handlers.AddOne(value = $.b)
        // This step depends on both previous steps
        product = handlers.Multiply(a = addedA.result, b = addedB.result)
        yield ParallelAdd(sumPlusTwo = product.result)
    }
}
''',
}


def _collect_workflows(node: dict, prefix: str = "") -> list[tuple[str, dict]]:
    """Collect all (qualified_name, workflow_dict) from compiled JSON."""
    results: list[tuple[str, dict]] = []

    for w in node.get("workflows", []):
        qname = f"{prefix}{w['name']}" if prefix else w["name"]
        results.append((qname, w))

    for decl in node.get("declarations", []):
        if decl.get("type") == "WorkflowDecl":
            qname = f"{prefix}{decl['name']}" if prefix else decl["name"]
            results.append((qname, decl))
        elif decl.get("type") == "Namespace":
            ns_prefix = f"{prefix}{decl['name']}."
            results.extend(_collect_workflows(decl, ns_prefix))

    for ns in node.get("namespaces", []):
        ns_prefix = f"{prefix}{ns['name']}."
        results.extend(_collect_workflows(ns, ns_prefix))

    return results


def seed_inline_source(name: str, source: str, store) -> int:
    """Seed a single inline AFL source. Returns workflow count."""
    from afl.emitter import JSONEmitter
    from afl.parser import AFLParser
    from afl.runtime.entities import (
        FlowDefinition,
        FlowIdentity,
        SourceText,
        WorkflowDefinition,
    )
    from afl.runtime.types import generate_id

    parser = AFLParser()
    ast = parser.parse(source, filename=f"{name}.afl")

    emitter = JSONEmitter(include_locations=False)
    program_json = emitter.emit(ast)
    program_dict = json.loads(program_json)

    workflows = _collect_workflows(program_dict)
    if not workflows:
        return 0

    now_ms = int(time.time() * 1000)
    flow_id = generate_id()

    flow = FlowDefinition(
        uuid=flow_id,
        name=FlowIdentity(name=name, path=SEED_PATH, uuid=flow_id),
        compiled_sources=[SourceText(name=f"{name}.afl", content=source)],
    )
    store.save_flow(flow)

    for qname, _wf_dict in workflows:
        wf_id = generate_id()
        workflow = WorkflowDefinition(
            uuid=wf_id,
            name=qname,
            namespace_id=SEED_PATH,
            facet_id=wf_id,
            flow_id=flow_id,
            starting_step="",
            version="1.0",
            date=now_ms,
        )
        store.save_workflow(workflow)

    return len(workflows)


def seed_example_directory(name: str, afl_files: list[str], store) -> int:
    """Seed an example directory's AFL files. Returns workflow count."""
    from afl.ast import Program
    from afl.emitter import JSONEmitter
    from afl.parser import AFLParser
    from afl.runtime.entities import (
        FlowDefinition,
        FlowIdentity,
        SourceText,
        WorkflowDefinition,
    )
    from afl.runtime.types import generate_id

    parser = AFLParser()
    programs = []
    source_parts = []

    for path in afl_files:
        with open(path) as f:
            text = f.read()
        source_parts.append(text)
        programs.append(parser.parse(text, filename=path))

    merged = Program.merge(programs)

    emitter = JSONEmitter(include_locations=False)
    program_json = emitter.emit(merged)
    program_dict = json.loads(program_json)

    workflows = _collect_workflows(program_dict)
    if not workflows:
        return 0

    now_ms = int(time.time() * 1000)
    flow_id = generate_id()
    combined_source = "\n".join(source_parts)

    flow = FlowDefinition(
        uuid=flow_id,
        name=FlowIdentity(name=name, path=SEED_PATH, uuid=flow_id),
        compiled_sources=[SourceText(name="source.afl", content=combined_source)],
    )
    store.save_flow(flow)

    for qname, _wf_dict in workflows:
        wf_id = generate_id()
        workflow = WorkflowDefinition(
            uuid=wf_id,
            name=qname,
            namespace_id=SEED_PATH,
            facet_id=wf_id,
            flow_id=flow_id,
            starting_step="",
            version="1.0",
            date=now_ms,
        )
        store.save_workflow(workflow)

    return len(workflows)


def clean_seeds(store) -> tuple[int, int]:
    """Remove all previously seeded flows and their workflows."""
    db = store._db
    flow_docs = list(db.flows.find({"name.path": SEED_PATH}, {"uuid": 1}))
    flow_ids = [doc["uuid"] for doc in flow_docs]

    workflows_deleted = 0
    if flow_ids:
        result = db.workflows.delete_many({"flow_id": {"$in": flow_ids}})
        workflows_deleted = result.deleted_count

    result = db.flows.delete_many({"name.path": SEED_PATH})
    flows_deleted = result.deleted_count

    # Also clean up legacy seed documents (from old seed.py format)
    legacy = db.flows.delete_many({"name": {"$regex": "^seed-"}})
    flows_deleted += legacy.deleted_count

    return flows_deleted, workflows_deleted


def seed_database():
    """Seed the database with example workflows."""
    from afl.runtime.mongo_store import MongoStore

    mongodb_url = os.environ.get("AFL_MONGODB_URL", "mongodb://localhost:27017")
    database = os.environ.get("AFL_MONGODB_DATABASE", "afl")

    logger.info("Connecting to %s/%s", mongodb_url, database)
    store = MongoStore(connection_string=mongodb_url, database_name=database)

    # Clean existing seed data first
    flows_del, wfs_del = clean_seeds(store)
    if flows_del > 0 or wfs_del > 0:
        logger.info("Cleaned %d flow(s) and %d workflow(s)", flows_del, wfs_del)

    total_flows = 0
    total_workflows = 0

    # 1. Seed inline examples
    logger.info("Seeding inline examples...")
    # chain-example and parallel-example depend on addone-example's namespace,
    # so combine all inline sources into a single compilation unit
    combined_source = "\n".join(INLINE_SOURCES.values())
    try:
        wf_count = seed_inline_source("inline-examples", combined_source, store)
        total_flows += 1
        total_workflows += wf_count
        logger.info("  inline-examples: %d workflows", wf_count)
    except Exception as e:
        logger.error("  inline-examples: ERROR: %s", e)

    # 2. Seed examples/ directories
    examples_dir = "/app/examples"
    if os.path.isdir(examples_dir):
        logger.info("Seeding example directories...")
        for entry in sorted(os.listdir(examples_dir)):
            afl_dir = os.path.join(examples_dir, entry, "afl")
            if not os.path.isdir(afl_dir):
                continue

            afl_files = sorted(glob.glob(os.path.join(afl_dir, "*.afl")))
            if not afl_files:
                continue

            try:
                wf_count = seed_example_directory(entry, afl_files, store)
                if wf_count > 0:
                    total_flows += 1
                    total_workflows += wf_count
                    logger.info("  %-20s %2d files  %3d workflows   OK",
                                entry, len(afl_files), wf_count)
                else:
                    logger.info("  %-20s %2d files    0 workflows   SKIP",
                                entry, len(afl_files))
            except Exception as e:
                logger.warning("  %-20s ERROR: %s", entry, e)

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Seed Complete!")
    logger.info("=" * 60)
    logger.info("Flows:     %d", total_flows)
    logger.info("Workflows: %d", total_workflows)
    logger.info("")
    logger.info("View the dashboard at: http://localhost:8080")
    logger.info("=" * 60)

    store.close()


if __name__ == "__main__":
    seed_database()
