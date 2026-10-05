from fastapi import FastAPI, UploadFile, File, HTTPException
from app.ingestion.file_detector import detect_file_type
from app.ingestion.text_extractor import extract_text

app = FastAPI(
    title="Enterprise Document Intelligence API",
    description="API for processing and analyzing enterprise documents.",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "message": "Enterprise Document Intelligence API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):

    file_type = detect_file_type(file.filename)

    if file_type == "unsupported":
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type"
        )

    file_bytes = await file.read()

    try:
        extracted_text = extract_text(
            file_bytes=file_bytes,
            file_type=file_type
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(error)}"
        )

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "detected_type": file_type,
        "file_size_bytes": len(file_bytes),
        "text_length": len(extracted_text),
        "text_preview": extracted_text[:1000]
    }