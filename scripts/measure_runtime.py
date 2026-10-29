"""Measure the real, pinned API inference path without scoring model accuracy.

Each model selection runs in a fresh Python process. Input variants are made
in memory from checked-in gallery display copies; no private images are read.
The output contains timing and resource data, never image bytes or scores.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/public/gallery/candidates/bird-display.jpg"
MODES = {
    "v3_e2": ["v3_e2"],
    "community_forensics": ["community_forensics"],
    "both": ["v3_e2", "community_forensics"],
}


def peak_rss_mb() -> float:
    """OS peak resident set, including native Torch/ONNX allocations."""
    if sys.platform == "win32":
        import ctypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return round(counters.PeakWorkingSetSize / 1_048_576, 1)
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(value / (1024 if sys.platform != "darwin" else 1_048_576), 1)


def physical_ram_mb() -> int | None:
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.ullTotalPhys / 1_048_576)
        return None
    try:
        return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1_048_576)
    except (ValueError, OSError, AttributeError):
        return None


def variants() -> dict[str, tuple[bytes, str]]:
    from PIL import Image

    source = SOURCE.read_bytes()
    with Image.open(BytesIO(source)) as original:
        rgb = original.convert("RGB")
        result = {"small_jpeg": (source, "image/jpeg")}
        for name, image, fmt, mime in (
            ("large_jpeg", rgb.resize((2000, 2000)), "JPEG", "image/jpeg"),
            ("png", rgb, "PNG", "image/png"),
            ("webp", rgb, "WEBP", "image/webp"),
        ):
            output = BytesIO()
            image.save(output, format=fmt)
            result[name] = (output.getvalue(), mime)
    return result


def summarize(samples: list[float]) -> dict[str, float | int]:
    return {
        "n": len(samples),
        "median_ms": round(statistics.median(samples), 1),
        "slowest_ms": round(max(samples), 1),
    }


def worker(mode: str) -> dict:
    worker_started = time.perf_counter()
    os.environ.setdefault("HF_HOME", str(ROOT / "model-cache"))
    os.environ.setdefault("IMAGE_DETECTOR_MODEL_CACHE", str(ROOT / "model-cache"))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["IOS_LOCAL_TEST_AUTH"] = "1"
    sys.path.insert(0, str(ROOT / "backend"))

    from fastapi.testclient import TestClient
    from PIL import Image

    from app.main import app
    from app.model import MODEL_FILENAME, MODEL_REVISION, MODEL_SHA256, get_detector
    from app.v3_e2 import (
        ARTIFACT_PATH,
        ARTIFACT_SHA256,
        MOBILE_WEIGHT_SHA256,
        get_e2_detector,
    )

    selected = MODES[mode]
    prepared = variants()
    process_started = time.perf_counter()
    cpu_started = time.process_time()
    loads = {}
    for key in selected:
        started = time.perf_counter()
        (get_e2_detector if key == "v3_e2" else get_detector)()
        loads[key] = round((time.perf_counter() - started) * 1000, 1)
    startup_ms = round((time.perf_counter() - worker_started) * 1000, 1)
    after_load_mb = peak_rss_mb()
    http = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 41234))

    def post_image(name: str, save: bool = False, token: str | None = None):
        data, mime = prepared[name]
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        started = time.perf_counter()
        response = http.post(
            "/api/analyze/compare",
            data={"models": selected, "save_to_history": str(save).lower()},
            files={"file": (name, data, mime)},
            headers=headers,
        )
        elapsed = (time.perf_counter() - started) * 1000
        if response.status_code != 200:
            raise RuntimeError(f"{name}: API returned {response.status_code}: {response.text[:200]}")
        result = response.json()
        if len(result["models"]) != len(selected) or any(item["status"] != "success" for item in result["models"]):
            raise RuntimeError(f"{name}: one or more pinned models failed")
        return round(elapsed, 1), result

    warm = {}
    for name in prepared:
        warm[name] = summarize([post_image(name)[0] for _ in range(3)])
    batch_start = time.perf_counter()
    for name in ("small_jpeg", "png", "webp", "large_jpeg") * 2:
        post_image(name)
    batch_ms = round((time.perf_counter() - batch_start) * 1000, 1)
    concurrent_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(post_image, ("small_jpeg", "large_jpeg")))
    concurrent_ms = round((time.perf_counter() - concurrent_start) * 1000, 1)
    inspector_start = time.perf_counter()
    response = http.post(
        "/api/inspect",
        data={"models": selected},
        files={"file": ("small.jpg", prepared["small_jpeg"][0], "image/jpeg")},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Inspector returned {response.status_code}")
    inspector_ms = round((time.perf_counter() - inspector_start) * 1000, 1)

    history = None
    if mode == "both":
        with tempfile.TemporaryDirectory(prefix="ios-sizing-") as directory:
            history_root = Path(directory) / "history"
            os.environ["IOS_HISTORY_ROOT"] = str(history_root)
            auth = http.post("/api/auth/local-test", json={"test_user": "alice"})
            auth.raise_for_status()
            token = auth.json()["access_token"]
            save_ms, saved = post_image("small_jpeg", save=True, token=token)
            if saved["history"]["status"] != "saved":
                raise RuntimeError("History save failed")
            saved_disk_bytes = sum(path.stat().st_size for path in history_root.rglob("*") if path.is_file())
            item_id = saved["history"]["history_id"]
            headers = {"Authorization": f"Bearer {token}"}
            started = time.perf_counter()
            fetched = http.get(f"/api/history/{item_id}/original", headers=headers)
            read_ms = round((time.perf_counter() - started) * 1000, 1)
            if fetched.content != prepared["small_jpeg"][0]:
                raise RuntimeError("Saved original differs from submitted bytes")
            started = time.perf_counter()
            deleted = http.delete(f"/api/history/{item_id}", headers=headers)
            delete_ms = round((time.perf_counter() - started) * 1000, 1)
            if deleted.status_code != 200:
                raise RuntimeError("History deletion failed")
            deleted_disk_bytes = sum(path.stat().st_size for path in history_root.rglob("*") if path.is_file())
            history = {"save_ms_includes_inference": save_ms, "retrieve_ms": read_ms,
                       "delete_ms": delete_ms, "original_bytes": len(fetched.content),
                       "disk_bytes_after_save": saved_disk_bytes,
                       "disk_bytes_after_delete": deleted_disk_bytes}
    http.close()

    input_metadata = {}
    for name, (data, mime) in prepared.items():
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
        input_metadata[name] = {
            "bytes": len(data), "mime_type": mime,
            "width": width, "height": height,
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    return {
        "mode": mode,
        "models": selected,
        "load_ms": loads,
        "startup_ms_from_worker_entry": startup_ms,
        "peak_rss_after_load_mb": after_load_mb,
        "peak_rss_final_mb": peak_rss_mb(),
        "cpu_seconds": round(time.process_time() - cpu_started, 2),
        "elapsed_seconds": round(time.perf_counter() - process_started, 2),
        "warm_api": warm,
        "batch_8_ms": batch_ms,
        "two_concurrent_ms": concurrent_ms,
        "two_concurrent_individual_ms": [item[0] for item in concurrent],
        "inspector_ms": inspector_ms,
        "history": history,
        "inputs": input_metadata,
        "artifacts": {
            "v3_e2_npz": {"path": str(ARTIFACT_PATH.relative_to(ROOT)), "sha256": ARTIFACT_SHA256},
            "mobilenet": {"sha256": MOBILE_WEIGHT_SHA256},
            "community_forensics": {"filename": MODEL_FILENAME, "revision": MODEL_REVISION,
                                    "sha256": MODEL_SHA256},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=MODES)
    parser.add_argument("--output", type=Path, default=ROOT / ".local" / "runtime-measurements.json")
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker)))
        return
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for mode in MODES:
        process = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker", mode],
            cwd=ROOT, capture_output=True, text=True, check=False,
            env={**os.environ, "HF_HUB_OFFLINE": "1"},
        )
        if process.returncode:
            raise RuntimeError(f"{mode} measurement failed:\n{process.stderr[-3000:]}")
        results.append(json.loads(process.stdout.strip().splitlines()[-1]))
    report = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "physical_ram_mb": physical_ram_mb(),
        "packages": {name: importlib.metadata.version(name) for name in
                     ("fastapi", "huggingface-hub", "numpy", "onnxruntime", "pillow", "torch", "torchvision")},
        "weight_downloads": "disabled; previously cached weights only",
        "source_note": "Checked-in gallery display copy and in-memory format/size variants; timings only",
        "results": results,
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
