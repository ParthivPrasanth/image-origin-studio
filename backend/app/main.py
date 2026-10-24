"""Local API. Uploaded bytes stay in memory and are discarded after inference."""

from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .model import MODEL_ID, MODEL_REVISION, SCORE_THRESHOLD, get_detector
from .validation import read_valid_image

logger = logging.getLogger(__name__)
app = FastAPI(title="Image Origin Studio API", version="0.1.0")


class AnalysisResult(BaseModel):
    prediction: str
    model_scores: dict[str, float]
    model_id: str = MODEL_ID
    model_revision: str = MODEL_REVISION
    ai_score_threshold: float = SCORE_THRESHOLD
    elapsed_ms: float = Field(ge=0)
    image_format: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_id": MODEL_ID, "model_revision": MODEL_REVISION}


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(file: UploadFile) -> AnalysisResult:
    data, image_format = await read_valid_image(file)
    started = perf_counter()
    try:
        detector = await run_in_threadpool(get_detector)
        scores = await run_in_threadpool(detector.predict, data)
    except Exception:
        logger.exception("Model inference failed")
        raise HTTPException(status_code=503, detail="The model could not process this image.") from None
    return AnalysisResult(
        prediction=scores.label,
        model_scores={"fake": scores.fake, "real": scores.real},
        ai_score_threshold=SCORE_THRESHOLD,
        elapsed_ms=round((perf_counter() - started) * 1000, 1),
        image_format=image_format,
    )
