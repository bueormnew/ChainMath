
"""
AI Benchmark Comparator
========================
Compares the model's JSON output against the answer key produced by generator.py.

Usage:
    python comparator.py

It will prompt for:
  1. Path to the model's answer JSON file
  2. Path to the answer key JSON file (benchmark_<seed>.json)
  3. Whether the model produced valid JSON on the first attempt (yes/no)

Scoring (0–100%):
  - Per-question score: weighted by difficulty (1–5).
  - Correctness tolerance: ±0.01 absolute or ±0.1% relative.
  - Order compliance: penalizes questions not sorted by ID in model output.
  - JSON format penalty: -10% if model failed to produce valid JSON on 1st try.
  - Final score is clamped to [0, 100].
"""

import json
import math
import os
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.5, 3: 2.5, 4: 4.0, 5: 6.0}
TOLERANCE_ABS = 0.01      # Absolute tolerance
TOLERANCE_REL = 0.001     # Relative tolerance (0.1%)
JSON_PENALTY_PCT = 10.0   # Fixed penalty if model failed JSON on first try


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_correct(model_val: float, expected: float) -> bool:
    """Check if model answer is within tolerance."""
    abs_err = abs(model_val - expected)
    if abs_err <= TOLERANCE_ABS:
        return True
    if expected != 0:
        rel_err = abs_err / abs(expected)
        if rel_err <= TOLERANCE_REL:
            return True
    return False


def check_id_order(model_answers: list[dict]) -> tuple[bool, int]:
    """
    Returns (is_sorted, n_out_of_order).
    is_sorted: True if ids are strictly ascending.
    n_out_of_order: count of positions where id[i] > id[i+1].
    """
    ids = [a.get("id") for a in model_answers if isinstance(a.get("id"), (int, float))]
    out_of_order = 0
    for i in range(len(ids) - 1):
        if ids[i] >= ids[i + 1]:
            out_of_order += 1
    return (out_of_order == 0), out_of_order


def parse_model_json(path: str) -> tuple[bool, Any]:
    """
    Try to load and validate the model's JSON.
    Returns (success, data).
    """
    try:
        data = load_json(path)
        if not isinstance(data, dict):
            return False, None
        if "answers" not in data:
            return False, None
        if not isinstance(data["answers"], list):
            return False, None
        return True, data
    except Exception as e:
        print(f"  [!] Could not parse model JSON: {e}")
        return False, None


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def score_benchmark(
    model_data: dict,
    key_data: dict,
    json_first_try: bool,
) -> dict:
    """
    Compute the full benchmark score.

    Returns a result dict with:
      - raw_score        : float [0, 100] before JSON penalty
      - json_penalty     : float (0 or 10)
      - final_score      : float [0, 100]
      - correct_count    : int
      - total_questions  : int
      - order_violations : int
      - order_penalty_pct: float
      - per_question     : list of per-question result dicts
    """

    # Build answer key dict: id -> {answer, difficulty}
    key_by_id: dict[int, dict] = {}
    for entry in key_data.get("answers", []):
        qid = entry["id"]
        key_by_id[qid] = {
            "answer": entry["answer"],
            "difficulty": entry["difficulty"],
        }

    total_questions = len(key_by_id)

    # Build model answer dict: id -> answer value
    model_answers_raw = model_data.get("answers", [])
    model_by_id: dict[int, Any] = {}
    for entry in model_answers_raw:
        try:
            qid = int(entry.get("id", -1))
            val = entry.get("answer", None)
            model_by_id[qid] = val
        except Exception:
            pass

    # Check ID ordering compliance
    is_sorted, order_violations = check_id_order(model_answers_raw)

    # Compute order penalty: each violation costs (0.5% of total score / total_questions)
    # Capped at 15% total order penalty
    if order_violations > 0:
        order_penalty_pct = min(15.0, order_violations * (15.0 / total_questions))
    else:
        order_penalty_pct = 0.0

    # Per-question scoring
    per_question = []
    weighted_earned = 0.0
    weighted_total = 0.0

    for qid, key_entry in key_by_id.items():
        expected = key_entry["answer"]
        diff = key_entry["difficulty"]
        weight = DIFFICULTY_WEIGHTS.get(diff, 1.0)

        if qid not in model_by_id:
            status = "missing"
            correct = False
            model_val = None
        else:
            raw_val = model_by_id[qid]
            try:
                model_val = float(raw_val)
                correct = is_correct(model_val, expected)
                status = "correct" if correct else "wrong"
            except (TypeError, ValueError):
                model_val = raw_val
                correct = False
                status = "invalid_type"

        earned = weight if correct else 0.0
        weighted_earned += earned
        weighted_total += weight

        per_question.append({
            "id": qid,
            "expected": expected,
            "model_answer": model_val,
            "difficulty": diff,
            "weight": weight,
            "correct": correct,
            "status": status,
        })

    # Raw correctness score (0–100)
    if weighted_total > 0:
        correctness_pct = (weighted_earned / weighted_total) * 100.0
    else:
        correctness_pct = 0.0

    # Apply order penalty
    after_order = correctness_pct * (1.0 - order_penalty_pct / 100.0)

    # JSON first-try penalty
    json_penalty = JSON_PENALTY_PCT if not json_first_try else 0.0

    # Final score (floor at 0)
    final_score = max(0.0, after_order - json_penalty)
    final_score = min(100.0, final_score)

    correct_count = sum(1 for p in per_question if p["correct"])

    return {
        "raw_correctness_pct": round(correctness_pct, 4),
        "order_violations": order_violations,
        "order_penalty_pct": round(order_penalty_pct, 4),
        "score_after_order": round(after_order, 4),
        "json_penalty_pct": round(json_penalty, 4),
        "final_score": round(final_score, 4),
        "correct_count": correct_count,
        "total_questions": total_questions,
        "answered_count": len(model_by_id),
        "per_question": sorted(per_question, key=lambda x: x["id"]),
    }


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(result: dict, json_first_try: bool):
    sep = "=" * 64
    print()
    print(sep)
    print("  AI BENCHMARK — EVALUATION REPORT")
    print(sep)
    print(f"  Questions in key      : {result['total_questions']}")
    print(f"  Questions answered    : {result['answered_count']}")
    print(f"  Correct answers       : {result['correct_count']} / {result['total_questions']}")
    print()
    print(f"  Weighted correctness  : {result['raw_correctness_pct']:.2f}%")
    print(f"  Order violations      : {result['order_violations']}")
    print(f"  Order penalty         : -{result['order_penalty_pct']:.2f}%")
    print(f"  Score after order     : {result['score_after_order']:.2f}%")
    print(f"  JSON first-try?       : {'YES' if json_first_try else 'NO'}")
    if result['json_penalty_pct'] > 0:
        print(f"  JSON format penalty   : -{result['json_penalty_pct']:.2f}%")
    print()
    print(f"  *** FINAL SCORE: {result['final_score']:.2f}% ***")
    print(sep)

    # Breakdown by difficulty
    print("\n  Results by difficulty:")
    print(f"  {'Difficulty':<12} {'Total':>7} {'Correct':>9} {'Acc%':>8}")
    print("  " + "-" * 40)
    for d in range(1, 6):
        qs = [p for p in result["per_question"] if p["difficulty"] == d]
        if not qs:
            continue
        n_correct = sum(1 for p in qs if p["correct"])
        acc = (n_correct / len(qs)) * 100 if qs else 0
        print(f"  {'★' * d:<12} {len(qs):>7} {n_correct:>9} {acc:>7.1f}%")

    # Show wrong/missing questions
    wrong = [p for p in result["per_question"] if not p["correct"]]
    if wrong:
        print(f"\n  Wrong/Missing ({len(wrong)} questions):")
        print(f"  {'ID':>4}  {'Expected':>12}  {'Got':>12}  {'Diff':>4}  Status")
        print("  " + "-" * 54)
        for p in wrong[:50]:  # limit to first 50 to avoid overflow
            got = str(p["model_answer"]) if p["model_answer"] is not None else "—"
            print(f"  {p['id']:>4}  {str(p['expected']):>12}  {got:>12}  {'★'*p['difficulty']:>4}  {p['status']}")
        if len(wrong) > 50:
            print(f"  ... and {len(wrong) - 50} more.")
    else:
        print("\n  All questions answered correctly!")

    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def prompt_file(label: str) -> str:
    while True:
        path = input(f"  {label}: ").strip().strip('"').strip("'")
        if os.path.isfile(path):
            return path
        print(f"  [!] File not found: '{path}'. Please try again.")


def main():
    print("=" * 64)
    print("  AI BENCHMARK COMPARATOR")
    print("=" * 64)
    print()
    print("  Provide file paths (with or without quotes):")
    model_path = prompt_file("Path to MODEL's answer JSON file")
    key_path = prompt_file("Path to ANSWER KEY JSON file (benchmark_<seed>.json)")

    print()
    print("  Did the model produce valid JSON on the FIRST attempt?")
    print("  (If it failed and you had to ask again or fix it manually, answer 'no')")
    while True:
        answer = input("  [yes/no]: ").strip().lower()
        if answer in ("yes", "y"):
            json_first_try = True
            break
        elif answer in ("no", "n"):
            json_first_try = False
            break
        else:
            print("  Please type 'yes' or 'no'.")

    print()
    print("  Loading files...")

    # Load model JSON
    ok, model_data = parse_model_json(model_path)
    if not ok:
        print("  [ERROR] Could not load model JSON. Check the file format.")
        sys.exit(1)

    # Load answer key
    try:
        key_data = load_json(key_path)
    except Exception as e:
        print(f"  [ERROR] Could not load answer key: {e}")
        sys.exit(1)

    print("  Computing scores...")
    result = score_benchmark(model_data, key_data, json_first_try)
    print_report(result, json_first_try)

    # Save detailed result JSON
    out_dir = os.path.dirname(model_path)
    out_path = os.path.join(out_dir, "evaluation_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        # Remove per-question question_text from key to keep output tidy
        export = {k: v for k, v in result.items() if k != "per_question"}
        export["per_question"] = result["per_question"]
        export["json_first_try"] = json_first_try
        json.dump(export, f, ensure_ascii=False, indent=2)
    print(f"\n  Detailed results saved to: {out_path}")


if __name__ == "__main__":
    main()
