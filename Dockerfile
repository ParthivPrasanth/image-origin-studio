FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/ios/.cache/huggingface \
    IMAGE_DETECTOR_MODEL_CACHE=/home/ios/.cache/image-origin-studio \
    IOS_HISTORY_ROOT=/tmp/ios-history

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 ios

WORKDIR /app
COPY backend/requirements-lock.txt /app/backend/requirements-lock.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements-lock.txt
COPY backend/app /app/backend/app
COPY backend/artifacts/v3_e2.npz /app/backend/artifacts/v3_e2.npz
RUN mkdir -p /home/ios/.cache/huggingface /home/ios/.cache/image-origin-studio \
    && chown -R ios:ios /home/ios

USER ios
WORKDIR /app/backend
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/health', timeout=3).read()" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
