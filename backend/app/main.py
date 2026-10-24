"""Local API. Uploaded bytes stay in memory and are discarded after inference."""

from __future__ import annotations

import logging
from time import perf_counter

from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .model import MODEL_ID, MODEL_REVISION, SCORE_THRESHOLD, get_detector
from .v3_e2 import (
    MODEL_ID as E2_MODEL_ID,
    MODEL_REVISION as E2_MODEL_REVISION,
    SCORE_THRESHOLD as E2_SCORE_THRESHOLD,
    get_e2_detector,
)
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


class ModelSuccess(BaseModel):
    model_key: Literal["v3_e2", "community_forensics"]
    status: Literal["success"] = "success"
    prediction: str
    model_scores: dict[str, float]
    model_id: str
    model_revision: str
    ai_score_threshold: float
    elapsed_ms: float = Field(ge=0)


class ModelError(BaseModel):
    model_key: Literal["v3_e2", "community_forensics"]
    status: Literal["error"] = "error"
    error: str


class ComparisonResult(BaseModel):
    image_format: str
    models: list[ModelSuccess | ModelError]


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


@app.post("/api/analyze/compare", response_model=ComparisonResult)
async def compare(
    file: UploadFile = File(...), models: list[str] = Form(...),
) -> ComparisonResult:
    allowed = {"v3_e2", "community_forensics"}
    if not models or len(models) > 2 or len(set(models)) != len(models) or set(models) - allowed:
        raise HTTPException(
            status_code=422,
            detail="Choose V3 E2, Community Forensics, or both once each.",
        )
    data, image_format = await read_valid_image(file)
    results: list[ModelSuccess | ModelError] = []
    for model_key in models:
        started = perf_counter()
        try:
            detector = await run_in_threadpool(
                get_e2_detector if model_key == "v3_e2" else get_detector
            )
            scores = await run_in_threadpool(detector.predict, data)
            model_id, revision, threshold = (
                (E2_MODEL_ID, E2_MODEL_REVISION, E2_SCORE_THRESHOLD)
                if model_key == "v3_e2"
                else (MODEL_ID, MODEL_REVISION, SCORE_THRESHOLD)
            )
            results.append(ModelSuccess(
                model_key=model_key,
                prediction=scores.label,
                model_scores={"fake": scores.fake, "real": scores.real},
                model_id=model_id,
                model_revision=revision,
                ai_score_threshold=threshold,
                elapsed_ms=round((perf_counter() - started) * 1000, 1),
            ))
        except Exception:
            logger.exception("%s inference failed", model_key)
            results.append(ModelError(
                model_key=model_key,
                error=f"{model_key.replace('_', ' ').title()} could not process this image.",
            ))
    return ComparisonResult(image_format=image_format, models=results)
