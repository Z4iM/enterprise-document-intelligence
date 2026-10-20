from io import BytesIO

import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageEnhance, ImageOps


def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = ImageOps.autocontrast(image)

    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)

    width, height = image.size
    image = image.resize((width * 2, height * 2))

    return image


def extract_image_text(file_bytes: bytes) -> str:
    image_file = BytesIO(file_bytes)

    image = Image.open(image_file)

    processed_image = preprocess_image(image)

    text = pytesseract.image_to_string(processed_image)

    return text.strip()


def extract_scanned_pdf_text(file_bytes: bytes) -> str:
    pages = convert_from_bytes(file_bytes)

    text_parts = []

    for page in pages:
        processed_page = preprocess_image(page)

        page_text = pytesseract.image_to_string(processed_page)

        if page_text.strip():
            text_parts.append(page_text.strip())

    return "\n".join(text_parts)