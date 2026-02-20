"""AWS Lambda event facet handlers.

Handles CreateFunction, InvokeFunction, UpdateFunctionCode, DeleteFunction,
ListFunctions, GetFunctionInfo, and PublishLayer event facets from the
aws.lambda namespace. Each handler makes real boto3 calls to LocalStack.
"""

import io
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from typing import Any

import boto3

log = logging.getLogger(__name__)

NAMESPACE = "aws.lambda"

LOCALSTACK_URL = os.environ.get("LOCALSTACK_URL", "http://localhost:4566")


def _lambda_client():
    """Create a boto3 Lambda client pointing at LocalStack."""
    return boto3.client(
        "lambda",
        endpoint_url=LOCALSTACK_URL,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def _iam_client():
    """Create a boto3 IAM client pointing at LocalStack."""
    return boto3.client(
        "iam",
        endpoint_url=LOCALSTACK_URL,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def _ensure_role() -> str:
    """Ensure a Lambda execution role exists in LocalStack, return its ARN."""
    iam = _iam_client()
    role_name = "afl-lambda-role"
    try:
        resp = iam.get_role(RoleName=role_name)
        return resp["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        trust_policy = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        })
        resp = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy,
            Path="/",
        )
        return resp["Role"]["Arn"]


def _create_zip_package(handler_code: str = "") -> bytes:
    """Build a minimal Lambda deployment zip in-memory."""
    if not handler_code:
        handler_code = (
            "def lambda_handler(event, context):\n"
            "    return {'statusCode': 200, 'body': 'Hello from AFL'}\n"
        )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", handler_code)
    return buf.getvalue()


def _create_function_handler(payload: dict) -> dict[str, Any]:
    """Create a Lambda function."""
    step_log = payload.get("_step_log")
    client = _lambda_client()
    role_arn = _ensure_role()
    function_name = payload.get("function_name", "afl-function")
    if step_log:
        step_log(f"CreateFunction: {function_name}")
    runtime = payload.get("runtime", "python3.12")
    handler = payload.get("handler", "lambda_function.lambda_handler")
    memory_mb = payload.get("memory_mb", 128)
    timeout_seconds = payload.get("timeout_seconds", 30)
    env_vars = payload.get("environment_vars", "")

    env_dict = {}
    if env_vars:
        for pair in env_vars.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                env_dict[k.strip()] = v.strip()

    resp = client.create_function(
        FunctionName=function_name,
        Runtime=runtime,
        Role=role_arn,
        Handler=handler,
        Code={"ZipFile": _create_zip_package()},
        MemorySize=int(memory_mb),
        Timeout=int(timeout_seconds),
        Environment={"Variables": env_dict} if env_dict else {"Variables": {}},
    )

    return {
        "config": {
            "function_name": resp["FunctionName"],
            "function_arn": resp["FunctionArn"],
            "runtime": resp.get("Runtime", runtime),
            "handler": resp.get("Handler", handler),
            "role_arn": resp.get("Role", role_arn),
            "memory_mb": resp.get("MemorySize", memory_mb),
            "timeout_seconds": resp.get("Timeout", timeout_seconds),
            "code_size": resp.get("CodeSize", 0),
            "last_modified": resp.get("LastModified", datetime.now(timezone.utc).isoformat()),
        },
    }


def _invoke_function_handler(payload: dict) -> dict[str, Any]:
    """Invoke a Lambda function."""
    step_log = payload.get("_step_log")
    client = _lambda_client()
    function_name = payload.get("function_name", "afl-function")
    if step_log:
        step_log(f"InvokeFunction: {function_name}")
    input_payload = payload.get("input_payload", "{}")
    invocation_type = payload.get("invocation_type", "RequestResponse")

    start = datetime.now(timezone.utc)
    resp = client.invoke(
        FunctionName=function_name,
        InvocationType=invocation_type,
        Payload=input_payload.encode("utf-8"),
    )
    duration = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    response_payload = ""
    if "Payload" in resp:
        response_payload = resp["Payload"].read().decode("utf-8")

    return {
        "result": {
            "function_name": function_name,
            "status_code": resp.get("StatusCode", 200),
            "payload": response_payload,
            "executed_version": resp.get("ExecutedVersion", "$LATEST"),
            "log_result": resp.get("LogResult", ""),
            "duration_ms": duration,
        },
    }


def _update_function_code_handler(payload: dict) -> dict[str, Any]:
    """Update a Lambda function's code."""
    step_log = payload.get("_step_log")
    client = _lambda_client()
    function_name = payload.get("function_name", "afl-function")
    if step_log:
        step_log(f"UpdateFunctionCode: {function_name}")
    s3_bucket = payload.get("s3_bucket", "")
    s3_key = payload.get("s3_key", "")

    if s3_bucket and s3_key:
        resp = client.update_function_code(
            FunctionName=function_name,
            S3Bucket=s3_bucket,
            S3Key=s3_key,
        )
    else:
        resp = client.update_function_code(
            FunctionName=function_name,
            ZipFile=_create_zip_package(),
        )

    return {
        "config": {
            "function_name": resp["FunctionName"],
            "function_arn": resp["FunctionArn"],
            "runtime": resp.get("Runtime", "python3.12"),
            "handler": resp.get("Handler", "lambda_function.lambda_handler"),
            "role_arn": resp.get("Role", ""),
            "memory_mb": resp.get("MemorySize", 128),
            "timeout_seconds": resp.get("Timeout", 30),
            "code_size": resp.get("CodeSize", 0),
            "last_modified": resp.get("LastModified", datetime.now(timezone.utc).isoformat()),
        },
    }


def _delete_function_handler(payload: dict) -> dict[str, Any]:
    """Delete a Lambda function."""
    step_log = payload.get("_step_log")
    client = _lambda_client()
    function_name = payload.get("function_name", "afl-function")
    if step_log:
        step_log(f"DeleteFunction: {function_name}")

    client.delete_function(FunctionName=function_name)

    return {
        "config": {
            "function_name": function_name,
            "function_arn": "",
            "runtime": "",
            "handler": "",
            "role_arn": "",
            "memory_mb": 0,
            "timeout_seconds": 0,
            "code_size": 0,
            "last_modified": datetime.now(timezone.utc).isoformat(),
        },
    }


def _list_functions_handler(payload: dict) -> dict[str, Any]:
    """List Lambda functions."""
    step_log = payload.get("_step_log")
    if step_log:
        step_log("ListFunctions")
    client = _lambda_client()
    max_items = payload.get("max_items", 50)
    marker = payload.get("marker", "")

    kwargs: dict[str, Any] = {"MaxItems": int(max_items)}
    if marker:
        kwargs["Marker"] = marker

    resp = client.list_functions(**kwargs)

    functions = resp.get("Functions", [])
    if functions:
        fn = functions[0]
        return {
            "config": {
                "function_name": fn["FunctionName"],
                "function_arn": fn["FunctionArn"],
                "runtime": fn.get("Runtime", ""),
                "handler": fn.get("Handler", ""),
                "role_arn": fn.get("Role", ""),
                "memory_mb": fn.get("MemorySize", 128),
                "timeout_seconds": fn.get("Timeout", 30),
                "code_size": fn.get("CodeSize", 0),
                "last_modified": fn.get("LastModified", ""),
            },
        }

    return {
        "config": {
            "function_name": "",
            "function_arn": "",
            "runtime": "",
            "handler": "",
            "role_arn": "",
            "memory_mb": 0,
            "timeout_seconds": 0,
            "code_size": 0,
            "last_modified": "",
        },
    }


def _get_function_info_handler(payload: dict) -> dict[str, Any]:
    """Get detailed function information."""
    step_log = payload.get("_step_log")
    client = _lambda_client()
    function_name = payload.get("function_name", "afl-function")
    if step_log:
        step_log(f"GetFunctionInfo: {function_name}")

    resp = client.get_function(FunctionName=function_name)
    config = resp.get("Configuration", {})

    return {
        "info": {
            "function_name": config.get("FunctionName", function_name),
            "function_arn": config.get("FunctionArn", ""),
            "runtime": config.get("Runtime", ""),
            "state": config.get("State", "Active"),
            "code_size": config.get("CodeSize", 0),
            "memory_mb": config.get("MemorySize", 128),
            "last_modified": config.get("LastModified", ""),
        },
    }


def _publish_layer_handler(payload: dict) -> dict[str, Any]:
    """Publish a Lambda layer version."""
    step_log = payload.get("_step_log")
    client = _lambda_client()
    layer_name = payload.get("layer_name", "afl-layer")
    if step_log:
        step_log(f"PublishLayer: {layer_name}")
    compatible_runtimes = payload.get("compatible_runtimes", "python3.12")
    description = payload.get("description", "")

    runtimes = [r.strip() for r in compatible_runtimes.split(",")]

    resp = client.publish_layer_version(
        LayerName=layer_name,
        Description=description,
        Content={"ZipFile": _create_zip_package("# layer content\n")},
        CompatibleRuntimes=runtimes,
    )

    return {
        "layer": {
            "layer_name": layer_name,
            "layer_arn": resp.get("LayerArn", ""),
            "version": resp.get("Version", 1),
            "code_size": resp.get("Content", {}).get("CodeSize", 0),
            "compatible_runtimes": compatible_runtimes,
        },
    }


# RegistryRunner dispatch adapter
_DISPATCH = {
    f"{NAMESPACE}.CreateFunction": _create_function_handler,
    f"{NAMESPACE}.InvokeFunction": _invoke_function_handler,
    f"{NAMESPACE}.UpdateFunctionCode": _update_function_code_handler,
    f"{NAMESPACE}.DeleteFunction": _delete_function_handler,
    f"{NAMESPACE}.ListFunctions": _list_functions_handler,
    f"{NAMESPACE}.GetFunctionInfo": _get_function_info_handler,
    f"{NAMESPACE}.PublishLayer": _publish_layer_handler,
}


def handle(payload: dict) -> dict:
    """RegistryRunner dispatch entrypoint."""
    facet_name = payload["_facet_name"]
    handler = _DISPATCH.get(facet_name)
    if handler is None:
        raise ValueError(f"Unknown facet: {facet_name}")
    return handler(payload)


def register_handlers(runner) -> None:
    """Register all facets with a RegistryRunner."""
    for facet_name in _DISPATCH:
        runner.register_handler(
            facet_name=facet_name,
            module_uri=f"file://{os.path.abspath(__file__)}",
            entrypoint="handle",
        )


def register_lambda_handlers(poller) -> None:
    """Register all Lambda event facet handlers with the poller."""
    for fqn, func in _DISPATCH.items():
        poller.register(fqn, func)
        log.debug("Registered lambda handler: %s", fqn)
