FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHON_DOTENV_DISABLED=1
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara poppler-utils libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements-runtime.txt ./
RUN pip install --no-cache-dir -r requirements-runtime.txt && pip check
RUN useradd --uid 10001 --create-home edi && mkdir -p /srv/data /srv/models && chown edi:edi /srv/data /srv/models
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/cache_retrieval_model.py ./cache_retrieval_model.py
USER edi
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
