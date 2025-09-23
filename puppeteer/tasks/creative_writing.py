import os
import json
from tqdm import tqdm

def load_dataset(data_limit=None):
    path = "./data/CW/creative_writing.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f]
    return data[:data_limit] if data_limit else data

def format_question(q, idx):
    question = "Concepts: " + ", ".join(q["concepts"]) + \
               "\nGenerate a sentence including all key concepts, grammatically correct and coherent."
    return {
        "type": "CW",
        "Question": question,
        "id": idx,
        "concepts": q["concepts"]
    }

def run(runner, evaluator, results_dir, mode, data_limit=None):
    dataset = load_dataset(data_limit)
    result_path = os.path.join(results_dir, "cw.jsonl")

    with open(result_path, "w", encoding="utf-8") as fd:
        for idx, q in enumerate(tqdm(dataset)):
            task = format_question(q, idx)
            final_ans = runner.run_reasoning(task)

            record = {
            "id": task["id"],
            "pred": final_ans
            }
            fd.write(json.dumps(record, ensure_ascii=False) + "\n")
