import anyio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Annotated, Any
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.prompts import base as prompt_base

from dispatcher_mcp_server import job_manager
from dispatcher_mcp_server.job_manager import (
    submit_job_impl,
    query_status_impl,
    cancel_job_impl,
    fetch_result_impl,
)

# Define the server lifespan context manager
@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Manage the server lifecycle, including a task group for background jobs."""
    print("Server lifespan starting...")
    async with anyio.create_task_group() as tg:
        print("Task group created.")
        # Pass the task group to the job manager
        job_manager.set_server_task_group(tg)
        try:
            yield # Server runs here
        finally:
            print("Server lifespan shutting down...")
            # Cancel the task group when the server stops
            tg.cancel_scope.cancel()
            print("Task group cancelled.")

# Create the FastMCP instance, passing the lifespan manager
mcp = FastMCP("Dispatcher MCP Server", lifespan=server_lifespan)
print("FastMCP server instance created with lifespan.")

@mcp.tool()
async def submit_job(
    command: Annotated[str, "The command line to execute for the task."],
    task_work_path: Annotated[str, "Relative path for the task's working directory within the submission's work_base."],
    forward_files: Annotated[list[str], "List of local file paths to upload to the task's working directory before execution."],
    backward_files: Annotated[list[str], "List of remote file paths (relative to task_work_path) to download after execution."],
    machine: Annotated[dict, "A dictionary describing the target machine configuration (e.g., batch type, context, connection details). Use get_machine_template for structure."],
    resources: Annotated[dict, "A dictionary describing the computational resources required (e.g., nodes, CPUs, GPUs, queue). Use get_resources_template for structure."],
    work_base: Annotated[str | None, "Optional. Base directory on the local machine where submission and task directories will be created. Defaults to './dispatcher_workdir/'."] = None
) -> dict:
    """
    Submits a computation job using dpdispatcher.

    This tool takes the command, file lists, machine configuration, and resource requirements,
    then submits the job via dpdispatcher. It returns a unique job ID for tracking.
    """
    print(f"[Server] Entering submit_job tool function for command: {command}")
    arguments = {
        "command": command,
        "task_work_path": task_work_path,
        "forward_files": forward_files,
        "backward_files": backward_files,
        "machine": machine,
        "resources": resources,
    }
    if work_base:
        arguments["work_base"] = work_base

    print(f"[Server] Prepared arguments for submit_job_impl: {arguments}")
    try:
        print("[Server] Calling submit_job_impl...")
        job_id = await submit_job_impl(arguments)
        print(f"Job submission successful, returning job_id: {job_id}")
        return {"job_id": job_id}
    except Exception as e:
        print(f"[Server] Error during submit_job_impl call: {e}", flush=True)
        import traceback
        traceback.print_exc() # Print full traceback
        # Return a structured error
        return {"error": f"Job submission failed in server: {e}"}


@mcp.tool()
async def query_status(
    job_id: Annotated[str, "The unique ID of the job previously returned by submit_job."]
) -> dict:
    """
    Queries the status of a previously submitted job.

    Returns the current status (e.g., 'queued', 'running', 'finished', 'failed').
    """
    print(f"Received query_status request for job_id: {job_id}")
    try:
        status = await query_status_impl(job_id)
        print(f"Query status successful for {job_id}, status: {status}")
        return {"job_id": job_id, "status": status}
    except Exception as e:
        print(f"Error querying status for job {job_id}: {e}")
        return {"job_id": job_id, "error": f"Status query failed: {e}"}

@mcp.tool()
async def cancel_job(
    job_id: Annotated[str, "The unique ID of the job to cancel."]
) -> dict:
    """
    Attempts to cancel a running or queued job by its ID.

    Returns the result of the cancellation request (e.g., 'cancellation_requested', 'not_found', 'error').
    Note: Actual cancellation depends on the HPC scheduler and job state.
    """
    print(f"Received cancel_job request for job_id: {job_id}")
    try:
        result = await cancel_job_impl(job_id)
        print(f"Cancel job successful for {job_id}, result: {result}")
        return {"job_id": job_id, "result": result}
    except Exception as e:
        print(f"Error cancelling job {job_id}: {e}")
        return {"job_id": job_id, "error": f"Cancellation failed: {e}"}


@mcp.tool()
async def fetch_result(
     job_id: Annotated[str, "The unique ID of the completed job whose results are to be fetched."]
) -> dict:
    """
    Fetches the list of expected result file paths for a completed job.

    Returns a list of file URIs or paths for the files specified in 'backward_files' during submission.
    """
    print(f"Received fetch_result request for job_id: {job_id}")
    try:
        files = await fetch_result_impl(job_id)
        print(f"Fetch result successful for {job_id}, files: {files}")
        return {"job_id": job_id, "files": files}
    except Exception as e:
        print(f"Error fetching results for job {job_id}: {e}")
        return {"job_id": job_id, "error": f"Fetching results failed: {e}"}


# --- Resources for Configuration Guidance ---

@mcp.resource("dpd://examples/machine/{type}")
async def resource_machine_example(type: str) -> dict | str:
    """
    Provides an example machine configuration dictionary for a given type.
    Supported types: 'local', 'slurm', 'bohrium'.
    """
    if type == "local":
        return {
            "batch_type": "Shell",
            "context_type": "LocalContext",
            "local_root": "./dpd_run_env",
            "remote_root": "./dpd_run_env"
        }
    elif type == "slurm":
        return {
            "batch_type": "Slurm",
            "context_type": "SSHContext",
            "local_root": "/local/path/to/workdir",
            "remote_root": "/remote/path/to/workdir",
            "remote_profile": {
                "hostname": "login.slurm.cluster",
                "username": "your_username",
                "port": 22,
                "key_filename": "/path/to/ssh/key" # Or use password/agent
            }
        }
    elif type == "bohrium":
        return {
            "batch_type": "OpenAPI",
            "context_type": "OpenAPIContext",
            "local_root": "/local/path/to/workdir",
            "remote_root": "/data/", # Example Bohrium path
            "remote_profile": {
                "username": "your_bohrium_email",
                "password": "YOUR_BOHRIUM_PASSWORD", # INSECURE!
                "project_id": 12345, # Your Bohrium project ID
                "platform": "bohrium"
            }
        }
    else:
        return f"Error: Unknown machine type '{type}'. Supported types: local, slurm, bohrium."

@mcp.resource("dpd://docs/resources")
async def resource_resources_docs() -> str:
    """Provides a description of common resource parameters."""
    # This could be loaded from a file or a more structured source
    return """
    Common Resource Parameters:
    - number_node (int): Number of nodes required (default: 1).
    - cpu_per_node (int): Number of CPU cores per node (default: 1).
    - gpu_per_node (int): Number of GPU devices per node (default: 0).
    - queue_name (str): Target queue, partition, or machine type name (required).
    - group_size (int): Number of tasks to group into one job (default: 1).
    - custom_flags (list[str]): Optional scheduler-specific directives (e.g., '#SBATCH --mem=4G').
    - module_list (list[str]): Optional modules to load.
    - source_list (list[str]): Optional environment scripts to source.
    - envs (dict): Optional environment variables to set.
    """

@mcp.resource("dpd://docs/task")
async def resource_task_docs() -> str:
    """Provides a description of common task parameters."""
    # This could be loaded from a file or a more structured source
    return """
    Common Task Parameters (for submit_job):
    - command (str): The command line to execute.
    - task_work_path (str): Relative directory for this task's files.
    - forward_files (list[str]): Local files to upload before running.
    - backward_files (list[str]): Remote files (in task_work_path) to download after running.
    - work_base (str, optional): Base directory on the client side for results.
    """

# --- Prompts for Configuration Guidance ---

@mcp.prompt()
async def configure_job() -> list[prompt_base.Message]:
    """Guides the LLM to interactively configure a dpdispatcher job submission."""
    return [
        prompt_base.AssistantMessage(
            "Okay, let's configure a job for dpdispatcher. I'll need details about the task, the machine it will run on, and the resources required."
        ),
        prompt_base.UserMessage(
            "First, tell me about the task itself. What command should be executed? What's a suitable working directory name for this task (e.g., 'relaxation_run')? Are there any input files to upload (forward_files)? What output files should be downloaded (backward_files)?"
            "\n(You can refer to dpd://docs/task for parameter details.)"
        ),
        # The conversation continues based on user response. The LLM would then ask about machine type,
        # potentially using ctx.read_resource('dpd://examples/machine/{type}') for examples,
        # then ask about resources using ctx.read_resource('dpd://docs/resources').
        # Finally, the LLM would gather all info and call submit_job.
    ]


if __name__ == "__main__":
    print("Starting Dispatcher MCP Server...")
    try:
        # mcp.run() will automatically handle the lifespan start/stop
        mcp.run()
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"\nServer encountered an error: {e}")
    finally:
        print("Server shutdown complete.")
