from typing import List, Dict, Any

# MCP工具的参数和返回值schema定义（JSON Schema格式）

submit_job_schema = {
    "name": "submit_job",
    "description": "提交一个计算任务到HPC集群",
    "inputSchema": {
        "type": "object",
        "required": ["command", "task_work_path", "forward_files", "backward_files", "machine", "resources"],
        "properties": {
            "command": {"type": "string", "description": "执行命令"},
            "task_work_path": {"type": "string", "description": "任务工作目录"},
            "forward_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "需要上传的文件列表"
            },
            "backward_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "需要下载的文件列表"
            },
            "machine": {
                "type": "object",
                "description": "HPC集群信息，参考dpdispatcher的Machine参数",
                "properties": {
                    "batch_type": {"type": "string"},
                    "context_type": {"type": "string"},
                    "local_root": {"type": "string"},
                    "remote_root": {"type": "string"},
                    "remote_profile": {"type": "object"}
                },
                "required": ["batch_type", "context_type", "local_root", "remote_root", "remote_profile"]
            },
            "resources": {
                "type": "object",
                "description": "资源配置，参考dpdispatcher的Resources参数",
                "properties": {
                    "number_node": {"type": "integer"},
                    "cpu_per_node": {"type": "integer"},
                    "gpu_per_node": {"type": "integer"},
                    "queue_name": {"type": "string"},
                    "group_size": {"type": "integer"}
                },
                "required": ["number_node", "cpu_per_node", "gpu_per_node", "queue_name", "group_size"]
            }
        }
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务ID"}
        },
        "required": ["job_id"]
    }
}

query_status_schema = {
    "name": "query_status",
    "description": "查询任务状态",
    "inputSchema": {
        "type": "object",
        "required": ["job_id"],
        "properties": {
            "job_id": {"type": "string", "description": "任务ID"}
        }
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "任务状态"}
        },
        "required": ["status"]
    }
}

cancel_job_schema = {
    "name": "cancel_job",
    "description": "取消任务",
    "inputSchema": {
        "type": "object",
        "required": ["job_id"],
        "properties": {
            "job_id": {"type": "string", "description": "任务ID"}
        }
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "result": {"type": "string", "description": "取消结果"}
        },
        "required": ["result"]
    }
}

fetch_result_schema = {
    "name": "fetch_result",
    "description": "获取任务结果文件",
    "inputSchema": {
        "type": "object",
        "required": ["job_id"],
        "properties": {
            "job_id": {"type": "string", "description": "任务ID"}
        }
    },
    "outputSchema": {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "结果文件内容或下载链接"
            }
        },
        "required": ["files"]
    }
}