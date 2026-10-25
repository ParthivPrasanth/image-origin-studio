"""Local image analysis and optional private-history API."""

from __future__ import annotations

import base64
import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager, suppress
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from .auth import issue_local_token, local_test_available, optional_identity, required_identity
from .history import (
    HistoryNotFound,
    HistoryQuotaExceeded,
    HistoryStorageError,
    HistoryStore,
)
from .model import (
    MODEL_ID,
    MODEL_REVISION,
    PREPROCESSING_RECIPE,
    SCORE_THRESHOLD,
    get_detector,
    input_view,
)
from .v3_e2 import (
    FFT_RECIPE,
    MOBILE_RECIPE,
    MODEL_ID as E2_MODEL_ID,
    MODEL_REVISION as E2_MODEL_REVISION,
    SCORE_THRESHOLD as E2_SCORE_THRESHOLD,
    get_e2_detector,
    image_view,
    mobile_input_view,
)
from .validation import read_valid_image

logger = logging.getLogger(__name__)


async def _history_cleanup_loop() -> None:
    while True:
        try:
            await run_in_threadpool(history_store().sweep)
        except Exception:
            logger.exception("Private history cleanup failed; will retry")
        await asyncio.sleep(3600)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    cleanup = asyncio.create_task(_history_cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


app = FastAPI(title="Image Origin Studio API", version="0.1.0", lifespan=_lifespan)


@app.middleware("http")
async def private_cache_control(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/history", "/api/auth")):
        response.headers["Cache-Control"] = "no-store"
    return response


class LocalTestSignIn(BaseModel):
    test_user: Literal["alice", "bob"]


@app.get("/api/auth/capabilities")
def auth_capabilities(request: Request) -> dict[str, bool]:
    return {"local_test_available": local_test_available(request)}


@app.post("/api/auth/local-test")
def local_test_sign_in(request: Request, body: LocalTestSignIn) -> dict[str, str | int]:
    return {"access_token": issue_local_token(request, body.test_user),
            "token_type": "bearer", "expires_in": 3600}


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
    preprocessing_recipe: str


class ModelError(BaseModel):
    model_key: Literal["v3_e2", "community_forensics"]
    status: Literal["error"] = "error"
    error: str
    model_id: str
    model_revision: str
    ai_score_threshold: float
    preprocessing_recipe: str


class InputMetadata(BaseModel):
    sha256: str
    width: int
    height: int
    image_format: str


class ComparisonResult(BaseModel):
    image_format: str
    input: InputMetadata
    analyzed_at: str
    models: list[ModelSuccess | ModelError]
    history: dict[str, str] | None = None


class InspectionView(BaseModel):
    key: str
    title: str
    width: int
    height: int
    recipe_id: str
    description: str
    preview_data_url: str
    note: str


class InspectionResult(BaseModel):
    input: InputMetadata
    views: list[InspectionView]


def _metadata(data: bytes, image_format: str) -> InputMetadata:
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
    return InputMetadata(
        sha256=hashlib.sha256(data).hexdigest(),
        width=width, height=height, image_format=image_format,
    )


def _view(
    key: str,
    title: str,
    image: Image.Image,
    recipe_id: str,
    description: str,
    note: str,
) -> InspectionView:
    output = BytesIO()
    image.save(output, format="PNG")
    return InspectionView(
        key=key,
        title=title,
        width=image.width,
        height=image.height,
        recipe_id=recipe_id,
        description=description,
        preview_data_url=(
            "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
        ),
        note=note,
    )


def _validate_models(models: list[str]) -> None:
    allowed = {"v3_e2", "community_forensics"}
    if (
        not models
        or len(models) > 2
        or len(set(models)) != len(models)
        or set(models) - allowed
    ):
        raise HTTPException(
            status_code=422,
            detail="Choose V3 E2, Community Forensics, or both once each.",
        )


@app.post("/api/inspect", response_model=InspectionResult)
async def inspect(
    file: UploadFile = File(...), models: list[str] = Form(...),
) -> InspectionResult:
    _validate_models(models)
    data, image_format = await read_valid_image(file)
    try:
        with Image.open(BytesIO(data)) as source:
            original = ImageOps.exif_transpose(source).convert("RGB")
        display = original.copy()
        display.thumbnail((512, 512), Image.Resampling.LANCZOS)
        views = [_view(
            "original", "Original upload", display, "original-display-exif-rgb-max512-v1",
            "Original file rendered upright using EXIF orientation and scaled to fit 512 px for display.",
            "Display copy only; the SHA-256 identifies the unmodified uploaded bytes.",
        )]
        if "v3_e2" in models:
            square = image_view(data)
            views.append(_view(
                "v3_e2_fft", "V3 E2 · FFT input", square, FFT_RECIPE,
                "EXIF orientation, RGB, centered square crop, Lanczos resize to 224 × 224; FFT64 is computed from this view.",
                "Exact RGB pixels used before grayscale conversion and FFT feature extraction.",
            ))
            mobile = mobile_input_view(square)
            views.append(_view(
                "v3_e2_mobile", "V3 E2 · MobileNet input", mobile, MOBILE_RECIPE,
                "The 224 × 224 square above enters TorchVision ImageNet V1 resize, center crop, then tensor normalization.",
                "Exact RGB pixels before tensor conversion and ImageNet normalization; normalized tensor values are not displayable colors.",
            ))
        if "community_forensics" in models:
            community = input_view(data)
            views.append(_view(
                "community_forensics", "Community Forensics input", community,
                PREPROCESSING_RECIPE,
                "EXIF orientation, RGB, bicubic resize to 440 px on the shorter side, then 384 × 384 center crop.",
                "Exact RGB pixels before ImageNet channel normalization; normalized tensor values are not displayable colors.",
            ))
        return InspectionResult(input=_metadata(data, image_format), views=views)
    except Exception:
        logger.exception("Input inspection failed")
        raise HTTPException(status_code=503, detail="Could not prepare model input views.") from None


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


@lru_cache(maxsize=8)
def _history_store(root: str) -> HistoryStore:
    return HistoryStore(Path(root))


def history_store() -> HistoryStore:
    root = os.getenv("IOS_HISTORY_ROOT") or str(
        Path(__file__).resolve().parents[2] / ".local" / "history"
    )
    return _history_store(root)


@app.post("/api/analyze/compare", response_model=ComparisonResult)
async def compare(
    request: Request,
    file: UploadFile = File(...),
    models: list[str] = Form(...),
    save_to_history: bool = Form(False),
) -> ComparisonResult:
    _validate_models(models)
    identity = optional_identity(request)
    if save_to_history and identity is None:
        raise HTTPException(status_code=401, detail="Sign in before saving an analysis.")
    data, image_format = await read_valid_image(file)
    input_metadata = _metadata(data, image_format)
    analyzed_at = datetime.now(timezone.utc).isoformat()
    results: list[ModelSuccess | ModelError] = []
    for model_key in models:
        started = perf_counter()
        model_id, revision, threshold, recipe = (
            (E2_MODEL_ID, E2_MODEL_REVISION, E2_SCORE_THRESHOLD,
             f"{FFT_RECIPE} + {MOBILE_RECIPE}")
            if model_key == "v3_e2"
            else (MODEL_ID, MODEL_REVISION, SCORE_THRESHOLD, PREPROCESSING_RECIPE)
        )
        try:
            detector = await run_in_threadpool(
                get_e2_detector if model_key == "v3_e2" else get_detector
            )
            scores = await run_in_threadpool(detector.predict, data)
            results.append(ModelSuccess(
                model_key=model_key,
                prediction=scores.label,
                model_scores={"fake": scores.fake, "real": scores.real},
                model_id=model_id,
                model_revision=revision,
                ai_score_threshold=threshold,
                elapsed_ms=round((perf_counter() - started) * 1000, 1),
                preprocessing_recipe=recipe,
            ))
        except Exception:
            logger.exception("%s inference failed", model_key)
            results.append(ModelError(
                model_key=model_key,
                error=f"{model_key.replace('_', ' ').title()} could not process this image.",
                model_id=model_id, model_revision=revision,
                ai_score_threshold=threshold,
                preprocessing_recipe=recipe,
            ))
    result = ComparisonResult(
        image_format=image_format, input=input_metadata,
        analyzed_at=analyzed_at, models=results,
    )
    if save_to_history and identity is not None:
        if not any(entry.status == "success" for entry in results):
            result.history = {"status": "not_saved", "reason": "No model succeeded."}
        else:
            mime_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[
                image_format
            ]
            try:
                record = await run_in_threadpool(
                    history_store().save, identity.sub, file.filename or "image",
                    mime_type, data, result.model_dump(exclude={"history"}), models,
                )
                result.history = {
                    "status": "saved", "history_id": record["history_id"],
                    "expires_at": record["expires_at"],
                }
            except HistoryQuotaExceeded:
                result.history = {"status": "not_saved", "reason": "History storage is full."}
            except (HistoryStorageError, OSError):
                logger.exception("Private history save failed")
                result.history = {"status": "not_saved", "reason": "Storage failed. Analysis was not saved."}
            except Exception:
                logger.exception("Unexpected private history save failure")
                result.history = {"status": "not_saved", "reason": "Storage failed. Analysis was not saved."}
    return result


@app.get("/api/history")
async def list_history(request: Request, cursor: str | None = None,
                       limit: int = Query(20, ge=1, le=50)) -> dict:
    identity = required_identity(request)
    try:
        return await run_in_threadpool(history_store().list, identity.sub, cursor, limit)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid history cursor.") from None


@app.get("/api/history/{history_id}")
async def get_history(request: Request, history_id: str) -> dict:
    identity = required_identity(request)
    try:
        return await run_in_threadpool(history_store().get, identity.sub, history_id)
    except HistoryNotFound:
        raise HTTPException(status_code=404, detail="History item unavailable.") from None


@app.get("/api/history/{history_id}/original")
async def get_history_original(request: Request, history_id: str) -> Response:
    identity = required_identity(request)
    try:
        record = await run_in_threadpool(history_store().get, identity.sub, history_id)
        original = await run_in_threadpool(
            history_store().read_original, identity.sub, history_id
        )
    except HistoryNotFound:
        raise HTTPException(status_code=404, detail="History item unavailable.") from None
    return Response(original, media_type=record["mime_type"],
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.delete("/api/history/account")
async def delete_history_account(request: Request) -> dict:
    identity = required_identity(request)
    return await run_in_threadpool(history_store().delete_account, identity.sub)


@app.delete("/api/history/{history_id}")
async def delete_history(request: Request, history_id: str) -> Response:
    identity = required_identity(request)
    try:
        result = await run_in_threadpool(history_store().delete, identity.sub, history_id)
        return JSONResponse(content=result)
    except HistoryNotFound:
        raise HTTPException(status_code=404, detail="History item unavailable.") from None
    except HistoryStorageError:
        logger.exception("Private history deletion pending retry")
        return JSONResponse(status_code=202, content={"deleted": False, "pending": True})
