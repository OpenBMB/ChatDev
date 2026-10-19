__all__ = ["WorkflowMetaInfo", "WorkflowRunResult", "run_workflow"]


def __getattr__(name):
    if name in __all__:
        from runtime.sdk import WorkflowMetaInfo, WorkflowRunResult, run_workflow

        values = {
            "WorkflowMetaInfo": WorkflowMetaInfo,
            "WorkflowRunResult": WorkflowRunResult,
            "run_workflow": run_workflow,
        }
        return values[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
