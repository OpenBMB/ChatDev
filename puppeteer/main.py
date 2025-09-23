import argparse
import os
import json
import yaml
from tasks.runner import BenchmarkRunner
from tasks.evaluator import BenchmarkEvaluator
from tasks import mmlu_pro, gsm_hard, srdd, creative_writing

def main():
    parser = argparse.ArgumentParser(description="Run benchmark tasks")
    parser.add_argument("task", choices=["MMLU-Pro", "gsm-hard", "SRDD", "CW"])
    parser.add_argument("mode", choices=["validation", "test"])
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--index", type=int, default=-1)
    parser.add_argument("--data_limit", type=int, default=1)
    parser.add_argument("--personas", type=str, default="personas/personas.jsonl")

    args = parser.parse_args()

    # load global config
    with open("config/global.yaml", "r") as f:
        global_config = yaml.safe_load(f)

    runner = BenchmarkRunner(args.personas, global_config)
    evaluator = BenchmarkEvaluator()

    results_dir = os.path.join(os.getcwd(), "results", f"{args.task}_{args.mode}")
    os.makedirs(results_dir, exist_ok=True)

    # change policy.json
    config_path = "config/policy.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    config["dataset_name"] = args.task
    config["dataset_mode"] = args.mode
    config['paths']["checkpoint_path"] = f"checkpoint/{args.task}_{args.mode}"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

    task_map = {
        "MMLU-Pro": mmlu_pro.run,
        "gsm-hard": gsm_hard.run,
        "SRDD": srdd.run,
        "CW": creative_writing.run,
    }

    if args.task in task_map:
        task_map[args.task](runner, evaluator, results_dir, args.mode, args.data_limit)
    else:
        print(f"Unknown task: {args.task}")

if __name__ == "__main__":
    main()