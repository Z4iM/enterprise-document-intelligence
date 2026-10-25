import argparse
import json
from collections import Counter
from pathlib import Path

from app.database.database import SessionLocal
from app.database.models import PolicyDocument
from app.validation.approved_rule_repository import load_approved_rules
from app.validation.evaluation_service import evaluate_verified_rules

BASE_DIR = Path(__file__).resolve().parent

POLICY_TRUTH_DIR = BASE_DIR / "policy_ground_truth"
PREDICTIONS_DIR = BASE_DIR / "predictions"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compare_metric(name, expected, actual) -> bool:
    passed = expected == actual

    print(f"{name}: {'PASS' if passed else 'FAIL'}")

    if not passed:
        print(f"  Expected: {expected}")
        print(f"  Actual:   {actual}")

    return passed


def action_counts(actions):
    """Compare required actions regardless of their order."""
    return Counter(
        (item["rule_id"], item["action"])
        for item in actions
    )


def rule_result_counts(results):
    """Compare every rule decision, including applicability."""
    return Counter(
        (
            item["rule_id"],
            item["applicable"],
            item["triggered"],
            item["status"],
        )
        for item in results
    )


def evaluate_policy_case(truth: dict, prediction: dict) -> bool:
    case_id = truth["case_id"]
    policy_id = truth["policy_id"]

    if prediction["case_id"] != case_id:
        raise ValueError(
            f"Prediction case ID mismatch for {case_id}"
        )

    # Read the existing policy and its verified, approved rules.
    with SessionLocal() as db:
        policy = db.get(PolicyDocument, policy_id)

        if policy is None:
            raise ValueError(
                f"Policy {policy_id} not found in local database"
            )

        approved_rules = load_approved_rules(
            db=db,
            policy_id=policy_id,
        )

        if not approved_rules:
            raise ValueError(
                f"No approved rules found for policy {policy_id}"
            )

        # Deterministic evaluation of the real Gemini prediction.
        actual = evaluate_verified_rules(
            document_data=prediction["predicted_fields"],
            approved_rules=approved_rules,
        )

    print(f"\n=== POLICY BENCHMARK: {case_id} ===")

    checks = [
        compare_metric(
            "Overall status",
            truth["expected_status"],
            actual["status"],
        ),
        compare_metric(
            "Rules evaluated",
            truth["expected_rules_evaluated"],
            actual["rules_evaluated"],
        ),
        compare_metric(
            "Applicable rules",
            truth["expected_applicable_rules"],
            actual["applicable_rules"],
        ),
        compare_metric(
            "Required actions",
            action_counts(truth["expected_required_actions"]),
            action_counts(actual["required_actions"]),
        ),
        compare_metric(
            "Individual rule decisions",
            rule_result_counts(truth["expected_rule_results"]),
            rule_result_counts(actual["rule_results"]),
        ),
    ]

    passed = sum(checks)

    print(f"\nChecks passed: {passed}/{len(checks)}")

    return all(checks)


def run_evaluation(provider: str):
    truth_paths = sorted(
        POLICY_TRUTH_DIR.glob("*_policy.json")
    )

    if not truth_paths:
        raise SystemExit("No policy ground-truth cases found.")

    results = []

    for path in truth_paths:
        truth = load_json(path)
        case_id = truth["case_id"]

        prediction_path = (
            PREDICTIONS_DIR / f"{case_id}_{provider}.json"
        )

        if not prediction_path.is_file():
            raise FileNotFoundError(
                f"Missing prediction: {prediction_path}"
            )

        prediction = load_json(prediction_path)

        passed = evaluate_policy_case(
            truth=truth,
            prediction=prediction,
        )

        results.append(passed)

    print("\n========== POLICY EVALUATION SUMMARY ==========")
    print(f"Provider: {provider}")
    print(f"Cases evaluated: {len(results)}")
    print(f"Cases passed: {sum(results)}")
    print(f"Cases failed: {len(results) - sum(results)}")

    if not all(results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--provider",
        default="gemini",
    )

    args = parser.parse_args()

    run_evaluation(args.provider)
