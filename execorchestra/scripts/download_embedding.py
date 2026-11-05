"""Download the pinned embedding assets without starting a service."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def download(*, tokenizer_only=False):
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer

    runtime = json.loads((ROOT / "configs/embedding_release.example.json").read_text(
        encoding="utf-8"))["runtime"]
    model, revision = runtime["model_id"], runtime["revision"]
    tokenizer_path = ROOT / ".cache/embedding-tokenizer"
    if tokenizer_only:
        tokenizer = AutoTokenizer.from_pretrained(model, revision=revision)
    else:
        model_path = ROOT / ".cache/embedding-model"
        snapshot_download(model, revision=revision, local_dir=str(model_path))
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    tokenizer.save_pretrained(str(tokenizer_path))
    print(f"Embedding assets ready: {model} @ {revision}")
    print(f"Tokenizer: {tokenizer_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-only", action="store_true",
                        help="Use an existing embedding endpoint; download only its tokenizer.")
    args = parser.parse_args()
    download(tokenizer_only=args.tokenizer_only)


if __name__ == "__main__":
    main()
