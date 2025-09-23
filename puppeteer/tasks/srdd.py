import os
import pandas as pd
from tqdm import tqdm
import json

def load_dataset(data_limit=None):
    data = pd.read_csv("./data/SRDD/SRDD.csv")
    data = data.sample(frac=1).reset_index(drop=True)
    return data[:data_limit] if data_limit else data

def format_question(row, idx):
    return {
        "type": "SRDD",
        "Question": "Develop a pythonic software following description:\n" + row["Description"],
        "id": idx
    }

def run(runner, evaluator, results_dir, mode, data_limit=None):
    dataset = load_dataset(data_limit)
    result_path = os.path.join(results_dir, "srdd.jsonl")

    with open(result_path, "w", encoding="utf-8") as fd:
        for idx, row in tqdm(dataset.iterrows(), total=len(dataset)):
            task = format_question(row, idx)
            final_ans = runner.run_reasoning(task)

            record = {
            "id": task["id"],
            "pred": final_ans
            }
            fd.write(json.dumps(record, ensure_ascii=False) + "\n")