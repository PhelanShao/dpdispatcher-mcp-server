# Dispatcher MCP Server

An MCP (Model Context Protocol) server that acts as a wrapper around the `dpdispatcher` library. It allows language models or other MCP clients to submit and manage computational jobs on local machines or HPC clusters supported by `dpdispatcher`.

## Features

*   Exposes `dpdispatcher` functionality via standard MCP tools.
*   **`submit_job`**: Submits a new computation job.
*   **`query_status`**: Checks the status of a submitted job.
*   **`cancel_job`**: Attempts to cancel a running or queued job.
*   **`fetch_result`**: Retrieves the paths of result files for a completed job.
*   Includes MCP Resources and Prompts to guide interactive job configuration.
*   Supports stdio transport for local integration (e.g., with Cline).

## Setup

1.  **Prerequisites**:
    *   Python 3.x
    *   `dpdispatcher` library installed (`pip install dpdispatcher`)
    *   `mcp` library installed (`pip install mcp`)
    *   `anyio` library installed (`pip install anyio`)

2.  **Clone/Place Files**: Ensure `fast_server.py` and `job_manager.py` (and `__init__.py`) are within a directory (e.g., `dispatcher_mcp_server`).

3.  **Configure `dpdispatcher`**: If submitting to remote HPCs or Bohrium, ensure `dpdispatcher` itself is correctly configured (e.g., SSH keys, Bohrium credentials).

## Running the Server

Navigate to the parent directory containing `dispatcher_mcp_server` and run:

```bash
python dispatcher_mcp_server/fast_server.py
```

The server will start and listen via stdio.

## Integration with MCP Clients (e.g., Cline)

Add the following configuration to your client's MCP settings (e.g., `mcp_settings.json` for Cline), adjusting paths as necessary:

```json
{
  "mcpServers": {
    "dispatcher-mcp-server": {
      "command": "python",
      "args": [
        "dispatcher_mcp_server/fast_server.py"
      ],
      "cwd": "/path/to/parent/directory/containing/dispatcher_mcp_server",
      "env": {
        "PYTHONPATH": "/path/to/parent/directory/containing/dispatcher_mcp_server"
      },
      "disabled": false
    }
  }
}
```

Restart the client to load the server.

## Usage

Interact with the server using an MCP client. You can directly call tools like `submit_job` by providing the necessary arguments (machine config, resources config, task details), or use the `configure_job` prompt to guide an LLM through an interactive configuration process. Helper resources like `dpd://examples/machine/{type}` are available for context.
