FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    WEBER_NO_BROWSER=1 \
    HOST=0.0.0.0 \
    PORT=7860

WORKDIR /app

COPY weber-rag/requirements.txt /app/weber-rag/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/weber-rag/requirements.txt

# Cache the query model in the image so restarts do not download ~2 GB again.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

COPY --chown=1000:1000 . /app
RUN mkdir -p /app/weber-rag/data/chroma_db \
    && chown -R 1000:1000 /app

USER 1000
EXPOSE 7860

CMD ["python", "weber-rag/serve.py"]
