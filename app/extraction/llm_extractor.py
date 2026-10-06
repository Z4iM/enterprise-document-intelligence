from app.llm.base import LLMProvider
from app.llm.prompts import build_extraction_prompt
from app.llm.validator import validate_llm_response


def extract_with_llm(
    text: str,
    document_type: str,
    provider: LLMProvider
) -> dict:

    prompt = build_extraction_prompt(
        text=text,
        document_type=document_type
    )

    response = provider.generate(prompt)

    return validate_llm_response(
        response=response,
        document_type=document_type
    )