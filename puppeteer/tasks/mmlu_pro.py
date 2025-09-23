import os
import string
import json
import pandas as pd
from tqdm import tqdm
from tasks.base.base_task import BaseTask

def load_dataset(mode, data_limit=None):
    path = os.path.join("data", "MMLU-Pro", f"{mode}.parquet")
    data = pd.read_parquet(path)
    return data[:data_limit] if data_limit else data

def format_question(task):
    options = [f"{letter}: {op}" for letter, op in zip(string.ascii_uppercase, task["options"])]
    prompt = f"The following are multiple choice questions (with answers) about {task['category']}."
    question = prompt + "\n" + task["question"] + "\n" + " ".join(options)
    return {
        "type": "MMLU-Pro",
        "Question": question,
        "Answer": task["answer"],
        "id": task["question_id"]
    }

def run(runner, evaluator, results_dir, mode, data_limit=None):
    dataset = load_dataset(mode, data_limit)
    result_path = os.path.join(results_dir, f"MMLU-Pro_{mode}.jsonl")
    acc = 0

    with open(result_path, "w", encoding="utf-8") as fd:
        for _, row in tqdm(dataset.iterrows(), total=len(dataset)):
            task = format_question(row)
            final_ans = runner.run_reasoning(task)
            flag = evaluator.check_mmlu(final_ans, task["Answer"])
            if flag: 
                acc += 1
            record = {
            "id": task["id"],
            "pred": final_ans,
            "correct": flag
            }
            fd.write(json.dumps(record, ensure_ascii=False) + "\n")
