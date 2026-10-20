
import json
import re

from app.llm.base import LLMProvider
from app.llm.validator import clean_json_response
from app.validation.evidence_extractor import extract_policy_evidence
from app.validation.rule_retry import retry_rule_extraction
from app.validation.rule_schemas import PolicyRule
from app.validation.source_verifier import (
    normalize_whitespace,
    verify_rule,
)


def extract_verified_rules(
    policy_text: str,
    chunk_id: str,
    provider: LLMProvider,
) -> dict:

    verified_rules = []
    rejected_rules = []

    # -----------------------------------------
    # STAGE 1: Extract supporting evidence
    # -----------------------------------------

    evidence = extract_policy_evidence(
        policy_text=policy_text,
        provider=provider,
    )

    if not evidence:
        return {
            "evidence": None,
            "verified_rules": [],
            "rejected_rules": [],
            "status": "no_evidence",
        }

    # Verify evidence exists in original policy
    if (
        normalize_whitespace(evidence)
        not in normalize_whitespace(policy_text)
    ):
        return {
            "evidence": evidence,
            "verified_rules": [],
            "rejected_rules": [
                {
                    "reason": "Evidence not found in source policy.",
                }
            ],
            "status": "verification_failed",
        }

    # -----------------------------------------
    # STAGE 2: Convert evidence into JSON
    # -----------------------------------------

    prompt = f"""
You are converting a policy statement into a
structured business rule.

SOURCE EVIDENCE:
{evidence}

SOURCE CHUNK ID:
{chunk_id}

Return exactly one JSON object with these fields:

{{
  "rule_id": "section number or descriptive ID",
  "category": "meal | hotel | ground_transportation | purchase | all_expenses",
  "field": "total",
  "operator": ">",
  "threshold": "0.00",
  "currency": "USD",
  "action": "requires_approval",
  "approval_role": null,
  "source_chunk_id": "{chunk_id}",
  "source_quote": null
}}

Instructions:
- Extract the condition that TRIGGERS the action.
- Do not extract a normal allowed range instead.
- "above", "over", "exceeds" mean >.
- "or more", "at least" mean >=.
- "below", "under" mean <.
- "up to", "at most" mean <=.
- Manager or director approval means requires_approval.
- Receipt or documentation required means requires_documentation.
- Explicit prohibition means policy_violation.
- Do not invent an approval requirement.
- Extract the approval role when explicitly stated.
- Do not invent values.
- Use the exact source chunk ID provided.
- Output only JSON.
CATEGORY RULES:
- Use "meal" for meals, food, and restaurant expenses.
- Use "hotel" for accommodation and hotel room rates.
- Use "ground_transportation" for taxis, rideshares, and ground transport.
- Use "purchase" for purchasing and procurement.
- Use "all_expenses" ONLY when the rule applies to all expense categories.
- Do not use generic values like "expense" or "expense category".
- Choose the category using the source evidence, including its section heading.
- Do not use "all_expenses" merely because a specific expense is mentioned.
"""
    raw_response = provider.generate(prompt)
    try:

        cleaned = clean_json_response(raw_response)

        parsed = json.loads(cleaned)

        if not isinstance(parsed, dict):
            raise TypeError("Expected a JSON object.")

        # Preserve original source evidence
        parsed["source_quote"] = evidence

        # -----------------------------------------
        # Recover explicitly stated approval role
        # -----------------------------------------

        if (
            parsed.get("action") == "requires_approval"
            and not parsed.get("approval_role")
        ):
            role_match = re.search(
                r"\b(manager|director|supervisor|department head)"
                r"\s+approval\b",
                evidence,
                flags=re.IGNORECASE,
            )

            if role_match:
                parsed["approval_role"] = (
                    role_match.group(1).lower()
                )

        # -----------------------------------------
        # Verify source chunk ID
        # -----------------------------------------

        if parsed.get("source_chunk_id") != chunk_id:
            raise ValueError("Unexpected source chunk ID.")

        # -----------------------------------------
        # Validate structure using Pydantic
        # -----------------------------------------

        rule = PolicyRule.model_validate(parsed)

    except (ValueError, TypeError) as error:
        return {
            "evidence": evidence,
            "verified_rules": [],
            "rejected_rules": [
                {
                    "reason": str(error),
                    "raw_response": locals().get(
                        "raw_response"
                    ),
                    "attempt": 1,
                }
            ],
            "status": "parsing_failed",
        }

    # -----------------------------------------
    # STAGE 3: Verify extracted rule
    # -----------------------------------------

    verification = verify_rule(rule, policy_text)

    if verification["verified"]:

        verified_rules.append(
            rule.model_dump(mode="json")
        )

    else:

        # Record the original rejected extraction
        rejected_rules.append(
            {
                "rule": rule.model_dump(mode="json"),
                "reason": verification["reason"],
                "attempt": 1,
            }
        )

        # -----------------------------------------
        # STAGE 4: Retry once with feedback
        # -----------------------------------------

        try:
            retry_response = retry_rule_extraction(
                provider=provider,
                source_evidence=evidence,
                rejected_rule=rule.model_dump(
                    mode="json"
                ),
                rejection_reason=verification["reason"],
            )

            cleaned_retry = clean_json_response(
                retry_response
            )

            retry_data = json.loads(cleaned_retry)

            if not isinstance(retry_data, dict):
                raise TypeError(
                    "Retry must return a JSON object."
                )

            # Never trust model-generated provenance
            retry_data["source_quote"] = evidence
            retry_data["source_chunk_id"] = chunk_id

            revised_rule = PolicyRule.model_validate(
                retry_data
            )

            # Verify revised rule against ORIGINAL policy
            retry_verification = verify_rule(
                revised_rule,
                policy_text,
            )

            if retry_verification["verified"]:

                verified_rules.append(
                    revised_rule.model_dump(
                        mode="json"
                    )
                )

            else:

                rejected_rules.append(
                    {
                        "rule": revised_rule.model_dump(
                            mode="json"
                        ),
                        "reason": retry_verification[
                            "reason"
                        ],
                        "attempt": 2,
                    }
                )

        except (ValueError, TypeError) as error:

            rejected_rules.append(
                {
                    "rule": None,
                    "reason": (
                        f"Retry failed: {error}"
                    ),
                    "attempt": 2,
                }
            )

    # -----------------------------------------
    # STAGE 5: Return final result
    # -----------------------------------------

    status = (
        "verified"
        if verified_rules
        else "verification_failed"
    )

    return {
        "evidence": evidence,
        "verified_rules": verified_rules,
        "rejected_rules": rejected_rules,
        "status": status,
    }
