__all__ = ["WorkflowMetaInfo", "WorkflowRunResult", "run_workflow"]


def __getattr__(name):
    if name in __all__:
        from runtime import sdk
        return getattr(sdk, name)
    raise AttributeError(f"module 'runtime' has no attribute {name!r}")
