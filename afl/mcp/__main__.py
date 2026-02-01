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

"""Entry point: python -m afl.mcp"""

from __future__ import annotations

import argparse
import logging
import sys


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="AFL MCP Server")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to AFL config file",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio"],
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: WARNING)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="FILE",
        help="Log to file (recommended for stdio transport) instead of stderr",
    )
    args = parser.parse_args()

    # Configure logging — file handler recommended for stdio transport
    # since stderr may interfere with JSON-RPC on some clients
    log_handlers: list[logging.Handler] = []
    if args.log_file:
        log_handlers.append(logging.FileHandler(args.log_file))
    else:
        log_handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=log_handlers,
    )

    try:
        import mcp  # noqa: F401
    except ImportError:
        print(
            "mcp is required. Install with: pip install 'agentflow[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)

    from mcp.server.stdio import stdio_server

    from .server import create_server

    server = create_server(config_path=args.config)

    import asyncio

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
