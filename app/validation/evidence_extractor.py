import re

from app.llm.base import LLMProvider


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_policy_evidence(
    policy_text: str,
    provider: LLMProvider
) -> str:

    # 1. Split original policy into sentences
    normalized_policy = normalize_text(policy_text)

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            normalized_policy
        )
        if sentence.strip()
    ]

    if not sentences:
        return ""

    # 2. Assign numbers to sentences
    numbered_sentences = "\n".join(
        f"{index}: {sentence}"
        for index, sentence in enumerate(
            sentences,
            start=1
        )
    )

    # 3. Ask Qwen to select a sentence number
    prompt = f"""
You are selecting evidence from company policies.

SENTENCES:
{numbered_sentences}

TASK:
Select the ONE sentence that explicitly states
a numerical condition and the action it triggers.

Prefer requirements such as:
- Manager approval
- Director approval
- Documentation required
- Prohibited expenses

Return ONLY the sentence number.

For example:
2

If no sentence qualifies, return 0.

Do not return the sentence text.
Do not explain.
"""

    response = provider.generate(prompt).strip()

    # 4. Accept only a plain integer
    if not re.fullmatch(r"\d+", response):
        return ""

    selected_index = int(response)

    if selected_index == 0:
        return ""

    if not 1 <= selected_index <= len(sentences):
        return ""

    # 5. Return original evidence, not LLM text
    return sentences[selected_index - 1]