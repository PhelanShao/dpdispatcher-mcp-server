import anyio
import click
from mcp.server.lowlevel import Server
import mcp.types as types
from dispatcher_mcp_server import job_manager

from dispatcher_mcp_server.schema import (
    submit_job_schema,
    query_status_schema,
    cancel_job_schema,
    fetch_result_schema,
)

app = Server("dispatcher-mcp-server")

# 工具调用路由
@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "submit_job":
        return await submit_job(arguments)
    elif name == "query_status":
        return await query_status(arguments)
    elif name == "cancel_job":
        return await cancel_job(arguments)
    elif name == "fetch_result":
        return await fetch_result(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")

# 工具列表
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=schema["name"],
            description=schema["description"],
            inputSchema=schema["inputSchema"],
        )
        for schema in [
            submit_job_schema,
            query_status_schema,
            cancel_job_schema,
            fetch_result_schema,
        ]
    ]

# 工具实现（待完善）
async def submit_job(arguments: dict):
    job_id = await job_manager.submit_job_impl(arguments)
    return {"job_id": job_id}

async def query_status(arguments: dict):
    job_id = arguments["job_id"]
    status = await job_manager.query_status_impl(job_id)
    return {"status": status}

async def cancel_job(arguments: dict):
    job_id = arguments["job_id"]
    result = await job_manager.cancel_job_impl(job_id)
    return {"result": result}

async def fetch_result(arguments: dict):
    job_id = arguments["job_id"]
    files = await job_manager.fetch_result_impl(job_id)
    return {"files": files}

@click.command()
@click.option("--port", default=8000, help="Port to listen on for SSE")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
def main(port: int, transport: str) -> int:
    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        import uvicorn

        uvicorn.run(starlette_app, host="0.0.0.0", port=port)
    else:
        from mcp.server.stdio import stdio_server

        async def arun():
            async with stdio_server() as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )

        anyio.run(arun)

    return 0