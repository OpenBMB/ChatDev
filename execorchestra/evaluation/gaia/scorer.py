"""GAIA scorer copied from AOrchestra with an SGAR compatibility adapter."""
from __future__ import annotations

import os
import re
import string
from typing import Any, Tuple


def normalize_number_str(number_str: str) -> float:
    """Normalize a number string by removing common formatting characters."""
    s = str(number_str or "")
    for ch in ["$", "%", ","]:
        s = s.replace(ch, "")
    try:
        return float(s)
    except Exception:
        return float("inf")


def normalize_str(input_str: str, remove_punct: bool = True) -> str:
    """Normalize a string by removing whitespace and optionally punctuation."""
    s = re.sub(r"\s", "", str(input_str or ""))
    if remove_punct:
        table = str.maketrans("", "", string.punctuation)
        return s.lower().translate(table)
    return s.lower()


def split_string(s: str, char_list: list[str] | None = None) -> list[str]:
    """Split a string by multiple delimiters."""
    chars = char_list or [",", ";"]
    pattern = f"[{''.join(chars)}]"
    return re.split(pattern, str(s or ""))


def question_scorer(model_answer: str | None, ground_truth: str | None) -> float:
    """Score an answer using the frozen AOrchestra/GAIA rule."""
    def is_float(elem: Any) -> bool:
        try:
            float(elem)
            return True
        except Exception:
            return False

    ma = "None" if model_answer is None else str(model_answer)
    gt = "" if ground_truth is None else str(ground_truth)
    if is_float(gt):
        return 1.0 if normalize_number_str(ma) == float(gt) else 0.0
    if any(ch in gt for ch in [",", ";"]):
        gt_elems = split_string(gt)
        ma_elems = split_string(ma)
        if len(gt_elems) != len(ma_elems):
            return 0.0
        cmp_list: list[bool] = []
        for a, b in zip(ma_elems, gt_elems):
            if is_float(b):
                cmp_list.append(normalize_number_str(a) == float(b))
            else:
                cmp_list.append(
                    normalize_str(a, remove_punct=False)
                    == normalize_str(b, remove_punct=False)
                )
        return 1.0 if all(cmp_list) else 0.0
    return 1.0 if normalize_str(ma) == normalize_str(gt) else 0.0


def extract_pred_text(prediction: Any) -> str:
    """Extract prediction text with AOrchestra's compatibility order."""
    if prediction is None:
        return ""
    if isinstance(prediction, dict):
        for key in ("final_answer", "answer", "output", "result", "text"):
            if key in prediction and prediction.get(key) is not None:
                return str(prediction.get(key))
        if "success" in prediction and not prediction.get("success"):
            return ""
        return str(prediction)
    return str(prediction)


def calculate_score(expected_output: Any, prediction: Any) -> Tuple[float, str]:
    """Calculate the frozen score after AOrchestra-compatible extraction."""
    pred_text = extract_pred_text(prediction)
    if expected_output is None:
        return (1.0 if pred_text else 0.0, pred_text)
    return (question_scorer(pred_text, str(expected_output)), pred_text)


def score_answer(model_answer: Any, expected_answer: Any) -> dict[str, Any]:
    """Return the frozen score in the existing SGAR record shape."""
    score, extracted = calculate_score(expected_answer, model_answer)
    return {
        "score": score,
        "correct": score == 1.0,
        "model_answer": extracted,
        "expected_answer": expected_answer,
    }


def resolve_gaia_attachment_path(file_name: str, file_root: str | None = None) -> str:
    """Resolve a GAIA attachment path using the AOrchestra API."""
    if not file_name:
        return ""
    if os.path.isabs(file_name):
        return file_name
    if file_root:
        return os.path.join(str(file_root).rstrip("/\\"), file_name)
    return os.path.join("benchmark", "gaia", "data", "Gaia", "2023", "validation", file_name)


def preprocess_file(task: str, file_name: str | None, file_root: str | None = None) -> str:
    """Preserve AOrchestra's attachment-hint compatibility helper."""
    if not file_name:
        return task
    hint_path = resolve_gaia_attachment_path(file_name, file_root=file_root)
    return (
        f"{task}\n"
        f"(* LOCAL FILES attached: {hint_path} - "
        f"Use ImageAnalysisAction for images, ParseAudioAction for audio, "
        f"ExecuteCodeAction for other files like txt/csv/xlsx/json/pdb)"
    )
