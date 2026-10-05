from io import BytesIO
from pypdf import PdfReader
from docx import Document
from pptx import Presentation


def extract_pdf_text(file_bytes: bytes) -> str:
    pdf_file = BytesIO(file_bytes)

    reader = PdfReader(pdf_file)

    text = []

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text.append(page_text)

    return "\n".join(text)


def extract_docx_text(file_bytes: bytes) -> str:
    docx_file = BytesIO(file_bytes)

    document = Document(docx_file)

    paragraphs = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            paragraphs.append(paragraph.text)

    return "\n".join(paragraphs)

def extract_txt_text(file_bytes: bytes, encoding: str = 'utf-8') -> str:
    try:
        return file_bytes.decode(encoding)
    except UnicodeDecodeError:
        # Fallback to a robust legacy encoding if UTF-8 fails
        return file_bytes.decode('latin-1', errors='ignore')

def extract_pptx_text(file_bytes: bytes) -> str:
    pptx_file = BytesIO(file_bytes)
    prs = Presentation(pptx_file)
    text_parts = []
    
    # 1. Loop through each slide
    for slide in prs.slides:
        # 2. Loop through every shape on the slide
        for shape in shape_generator(slide):
            # 3. Check if the shape contains text
            if hasattr(shape, "text_frame") and shape.text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    if paragraph.text.strip():
                        text_parts.append(paragraph.text.strip())
                        
    return "\n".join(text_parts)

def shape_generator(slide):
    """Helper function to find shapes, including those nested inside groups."""
    for shape in slide.shapes:
        if shape.shape_type == 6:  # 6 represents a GroupShape
            for sub_shape in shape.shapes:
                yield sub_shape
        else:
            yield shape

def extract_text(file_bytes: bytes, file_type: str) -> str:

    if file_type == "pdf":
        return extract_pdf_text(file_bytes)

    if file_type == "docx":
        return extract_docx_text(file_bytes)

    if file_type == "txt":
        return extract_txt_text(file_bytes)

    if file_type == "pptx":
        return extract_pptx_text(file_bytes)

    if file_type == "image":
        return ""

    raise ValueError(f"Unsupported extraction type: {file_type}")