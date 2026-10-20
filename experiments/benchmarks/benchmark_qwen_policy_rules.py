import csv
import json
import time
from pathlib import Path

from app.llm.http_provider import HTTPModelProvider
from app.validation.two_stage_extractor import extract_verified_rules
from app.validation.rule_schemas import PolicyRule
from app.validation.rule_evaluator import evaluate_rule
from app.validation.category_normalizer import normalize_category


DATASET_PATH = Path("tests/data/policy_benchmark.json")
RESULTS_DIR = Path("experiments/results")

MODEL_NAME = "Qwen2.5-3B-Instruct"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def run_benchmark():

    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        dataset = json.load(file)

    provider = HTTPModelProvider()

    results = []

    for index, case in enumerate(dataset, start=1):

        print(
            f"\n[{index}/{len(dataset)}] "
            f"Testing {case['id']}"
        )

        start_time = time.perf_counter()

        # Run our two-stage extraction pipeline
        try:
            extraction = extract_verified_rules(
                policy_text=case["policy_text"],
                chunk_id=case["id"],
                provider=provider
            )

            error = None

        except Exception as exc:
            extraction = {
                "status": "error",
                "verified_rules": [],
                "rejected_rules": [],
                "evidence": None
            }
            error = str(exc)

        elapsed = time.perf_counter() - start_time

        verified_rules = extraction.get(
            "verified_rules", []
        )

        # The current extractor handles one rule at a time.
        rule = None

        if len(verified_rules) == 1:
            rule = PolicyRule.model_validate(
                verified_rules[0]
            )

        verification_passed = rule is not None

        # Evaluate only verified rules
        evaluation = None

        if rule is not None:
            document = {
                "expense_category": case["category"],
                "total": case["test_amount"]
            }

            # Benchmark compatibility:
            # This dataset represents one expense amount per document.
            # In production, fields must be mapped using their true meaning.
            if rule.field == "amount":
                document["amount"] = case["test_amount"]

            if rule.field == "room_rate" and case["category"] == "hotel":
                document["room_rate"] = case["test_amount"]

            evaluation = evaluate_rule(
                rule=rule,
                document_data=document
            )

        # Compare extracted rule against ground truth
        operator_correct = (
            rule.operator == case["expected_operator"]
            if rule else False
        )

        threshold_correct = (
            rule.threshold ==
            PolicyRule.model_validate({
                "rule_id": "expected",
                "category": case["category"],
                "field": "total",
                "operator": case["expected_operator"],
                "threshold": case["expected_threshold"],
                "action": case["expected_action"],
                "approval_role": case["expected_approval_role"],
                "source_chunk_id": case["id"]
            }).threshold
            if rule else False
        )

        expected_scope = case.get(
            "expected_rule_scope",
            case["category"],
        )

        category_correct = (
            normalize_category(rule.category)
            == normalize_category(expected_scope)
            if rule else False
        )

        action_correct = (
            rule.action == case["expected_action"]
            if rule else False
        )

        approval_role_correct = (
            rule.approval_role ==
            case["expected_approval_role"]
            if rule else False
        )

        decision_correct = (
            evaluation is not None
            and evaluation.applicable
            and evaluation.triggered == case["expected_triggered"]
        )

        result = {
            "id": case["id"],
            "model": MODEL_NAME,
            "extraction_status": extraction["status"],
            "verification_passed": verification_passed,
            "operator_correct": operator_correct,
            "threshold_correct": threshold_correct,
            "category_correct": category_correct,
            "action_correct": action_correct,
            "approval_role_correct": approval_role_correct,
            "decision_correct": decision_correct,
            "latency_seconds": round(elapsed, 3),
            "extracted_rule": (
                rule.model_dump(mode="json")
                if rule else None
            ),
            "rejected_rules": extraction.get(
                "rejected_rules", []
            ),
            "error": error
        }

        results.append(result)

        print(
            "Verification:",
            "PASS" if verification_passed else "FAIL"
        )

        print(
            "Decision:",
            "PASS" if decision_correct else "FAIL"
        )

        print(
            "Latency:",
            round(elapsed, 2),
            "seconds"
        )

    # -----------------------------------------
    # Save detailed JSON results
    # -----------------------------------------

    json_path = RESULTS_DIR / "qwen_3b_benchmark.json"

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            indent=2
        )

    # -----------------------------------------
    # Save summary CSV
    # -----------------------------------------

    csv_path = RESULTS_DIR / "qwen_3b_benchmark.csv"

    metric_names = [
        "verification_passed",
        "operator_correct",
        "threshold_correct",
        "category_correct",
        "action_correct",
        "approval_role_correct",
        "decision_correct"
    ]

    summary = {
        metric: (
            sum(bool(row[metric]) for row in results)
            / len(results)
            if results else 0
        )
        for metric in metric_names
    }

    summary["average_latency_seconds"] = (
        sum(row["latency_seconds"] for row in results)
        / len(results)
        if results else 0
    )

    with open(csv_path, "w", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        writer.writerow(["Metric", "Value"])

        for metric, value in summary.items():
            writer.writerow([metric, round(value, 4)])

    print("\n==============================")
    print("BENCHMARK SUMMARY")
    print("==============================")

    for metric, value in summary.items():
        if metric == "average_latency_seconds":
            print(f"{metric}: {value:.2f}s")
        else:
            print(f"{metric}: {value:.1%}")

    print("\nDetailed results:", json_path)
    print("Summary CSV:", csv_path)


if __name__ == "__main__":
    run_benchmark()