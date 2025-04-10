import uuid
import os
from dpdispatcher import Machine, Resources, Task, Submission
import anyio
import anyio.to_thread

job_db = {}
server_task_group = None # Global variable to hold the server's task group

def set_server_task_group(tg: anyio.abc.TaskGroup):
    """Sets the task group managed by the server's lifespan."""
    global server_task_group
    server_task_group = tg
    print("Server task group has been set in job_manager.")

def generate_job_id():
    return str(uuid.uuid4())

def create_submission(arguments: dict) -> Submission:
    """Creates a dpdispatcher Submission object from arguments."""
    machine = Machine(**arguments["machine"])
    resources = Resources(**arguments["resources"])

    task = Task(
        command=arguments["command"],
        task_work_path=arguments["task_work_path"],
        forward_files=arguments["forward_files"],
        backward_files=arguments["backward_files"],
        # Add optional outlog/errlog if needed, based on schema or defaults
        # outlog=arguments.get("outlog", "out.log"),
        # errlog=arguments.get("errlog", "err.log"),
    )

    # Ensure work_base exists or handle creation appropriately
    work_base = arguments.get("work_base", "./dispatcher_workdir/")
    # os.makedirs(work_base, exist_ok=True) # Consider where this should happen

    submission = Submission(
        work_base=work_base,
        machine=machine,
        resources=resources,
        task_list=[task],
    )
    return submission

async def submit_job_impl(arguments: dict) -> str:
    """Submits a job using dpdispatcher in a background thread managed by the server task group."""
    if server_task_group is None:
        raise RuntimeError("Server task group not initialized. Ensure server is run with lifespan.")

    print("[Manager] Entering submit_job_impl...")
    try:
        print("[Manager] Calling create_submission...")
        submission = create_submission(arguments)
        print("[Manager] Submission object created successfully.")
    except Exception as e:
        print(f"[Manager] Error creating submission: {e}")
        import traceback
        traceback.print_exc()
        raise ValueError(f"Failed to create submission object: {e}")

    job_id = generate_job_id()
    job_db[job_id] = submission
    print(f"Created job with internal ID: {job_id}")

    async def run_submission_in_thread():
        """Wrapper to run the blocking submission call in a thread."""
        print(f"[BG Task {job_id}] Starting background submission task...")
        try:
            print(f"[BG Task {job_id}] Calling submission.run_submission via run_sync...")
            # This blocks the background thread until the HPC job completes
            await anyio.to_thread.run_sync(submission.run_submission)
            print(f"[BG Task {job_id}] submission.run_submission finished successfully.")
            # Note: Status in job_db[job_id] should now reflect completion.
        except Exception as e:
            print(f"[BG Task {job_id}] Error during submission.run_submission: {e}")
            import traceback
            traceback.print_exc()
            # Optionally update the status in job_db to reflect failure
            # For now, just log the error. Query status will show based on job files/state.
        except anyio.get_cancelled_exc_class():
             print(f"[BG Task {job_id}] Background submission task cancelled.")
             # Perform any necessary cleanup for cancellation if possible

    # Start the blocking call in a background thread managed by the server's task group
    try:
        print(f"[Manager] Scheduling background task for job {job_id}...")
        server_task_group.start_soon(run_submission_in_thread)
        print(f"[Manager] Background task for job {job_id} scheduled successfully.")
    except Exception as e:
        print(f"[Manager] Error starting background task for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        # Clean up if task start fails
        if job_id in job_db: del job_db[job_id]
        raise RuntimeError(f"Failed to start background submission task: {e}")

    return job_id

def get_submission(job_id: str) -> Submission | None:
    """Retrieves the Submission object for a given job ID."""
    return job_db.get(job_id)

async def query_status_impl(job_id: str) -> str:
    """Queries the status of the job based on the Submission object state."""
    print(f"Querying status for job {job_id}")
    submission = get_submission(job_id)
    if submission is None:
        print(f"Job {job_id} not found.")
        return "not_found"

    # dpdispatcher's Submission/Job status might be updated by run_submission.
    # This relies on the background task having updated the state.
    # A more robust implementation might need to query the HPC system directly.
    try:
        # Refresh status if dpdispatcher provides a method
        # await anyio.to_thread.run_sync(submission.update_status) # Hypothetical non-blocking update

        statuses = [job.status for job in submission.jobs]
        print(f"Job statuses for {job_id}: {statuses}")
        if not statuses:
             return "unknown (no jobs)"
        if all(s == "finished" for s in statuses):
            return "finished"
        elif any(s == "failed" for s in statuses):
             return "failed"
        elif any(s == "terminated" for s in statuses):
             return "terminated" # Or cancelled
        elif any(s == "running" for s in statuses):
            return "running"
        elif any(s == "queued" for s in statuses):
            return "queued"
        else:
            # Consider other statuses dpdispatcher might have
            return f"unknown ({','.join(statuses)})"
    except Exception as e:
        print(f"Error querying status for job {job_id}: {e}")
        return "error_querying_status"


async def cancel_job_impl(job_id: str) -> str:
    """Attempts to cancel the running job."""
    print(f"Attempting to cancel job {job_id}")
    submission = get_submission(job_id)
    if submission is None:
        print(f"Job {job_id} not found for cancellation.")
        return "not_found"
    try:
        # This needs to interact with the HPC scheduler.
        # job.cancel() might do this depending on the machine implementation.
        # Running it in a thread as it might block.
        await anyio.to_thread.run_sync(lambda: [job.cancel() for job in submission.jobs])
        print(f"Cancellation requested for job {job_id}.")
        # Note: Actual cancellation depends on the scheduler and job state.
        # Status might change to 'terminated' or similar after a delay.
        return "cancellation_requested"
    except Exception as e:
        print(f"Error cancelling job {job_id}: {e}")
        return "error"

async def fetch_result_impl(job_id: str) -> list[str]:
    """Fetches the paths of the expected result files."""
    print(f"Fetching results for job {job_id}")
    submission = get_submission(job_id)
    if submission is None:
        print(f"Job {job_id} not found for fetching results.")
        return []

    result_files_info = []
    try:
        # Ensure work_base and task_path are correctly resolved
        base_path = os.path.abspath(submission.work_base)

        for job in submission.jobs:
            task_path = job.task_path # Relative to work_base
            work_dir = os.path.join(base_path, task_path)

            for f in job.backward_files:
                # f should be the relative path within the task's work_dir
                file_path = os.path.join(work_dir, f)
                if os.path.exists(file_path):
                    # Return a file URI or some identifier, not just local path
                    # For now, return the path and existence status
                    result_files_info.append(f"file://{file_path} (exists)")
                    print(f"Result file found: {file_path}")
                else:
                    result_files_info.append(f"file://{file_path} (not found)")
                    print(f"Result file not found: {file_path}")

    except Exception as e:
        print(f"Error fetching results for job {job_id}: {e}")
        return [f"Error fetching results: {e}"]

    return result_files_info