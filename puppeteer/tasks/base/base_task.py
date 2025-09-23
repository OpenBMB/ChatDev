import os
from utils.file_utils import write_jsonl

class BaseTask:
    def __init__(self, runner, evaluator):
        self.runner = runner
        self.evaluator = evaluator

    def write_result(self, fd, task_id, final_ans, true_ans=None, flag=None):
        record = {
            "task_id": task_id,
            "final_ans": final_ans,
        }
        if true_ans is not None:
            record["true_ans"] = true_ans
        if flag is not None:
            record["flag"] = flag
        write_jsonl(fd, record)