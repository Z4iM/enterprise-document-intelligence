import re

HEADING_PATTERN = re.compile(
    r"^\d+(?:\.\d+)*\.?\s+.+$"
)


def chunk_text(
    text: str,
    max_chunk_size: int = 1400
) -> list[str]:

    if not text or not text.strip():
        return []

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [
        line.strip()
        for line in text.split("\n")
        if line.strip()
    ]

    sections = []

    current_section = []

    # -----------------------------------------
    # 1. Split document using numbered headings
    # -----------------------------------------

    for line in lines:

        is_heading = bool(
            HEADING_PATTERN.match(line)
        )

        if is_heading and current_section:

            sections.append(
                "\n".join(current_section)
            )

            current_section = [line]

        else:

            current_section.append(line)

    if current_section:

        sections.append(
            "\n".join(current_section)
        )

    # -----------------------------------------
    # 2. Split oversized sections safely
    # -----------------------------------------

    final_chunks = []

    for section in sections:

        if len(section) <= max_chunk_size:

            final_chunks.append(section)

            continue

        section_lines = section.split("\n")

        # Keep heading in every subchunk
        heading = section_lines[0]

        body_lines = section_lines[1:]

        current_chunk = heading

        for line in body_lines:

            candidate = (
                current_chunk
                + "\n"
                + line
            )

            if len(candidate) > max_chunk_size:

                final_chunks.append(
                    current_chunk.strip()
                )

                current_chunk = (
                    heading
                    + "\n"
                    + line
                )

            else:

                current_chunk = candidate

        if current_chunk.strip():

            final_chunks.append(
                current_chunk.strip()
            )

    return final_chunks