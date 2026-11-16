"""Model API sentimen + metrik Prometheus untuk 3 layer monitoring ML.

Layer 1 (sistem) : request, status HTTP, latensi, memori proses
Layer 2 (model)  : distribusi prediksi, confidence, rasio OOV, drift PSI
Layer 3 (bisnis) : umpan balik pengguna (prediksi dikoreksi = manual override)

Endpoint:
  GET  /           panel simulasi untuk kelas
  POST /predict    {"text": "..."}
  POST /feedback   {"predicted": "positif", "actual": "negatif"}
  POST /simulate   {"mode": "normal" | "drift" | "stop", "duration_s": 180, "rps": 5}
  POST /chaos      {"delay_ms": 800, "error_ratio": 0.2}
  GET  /health     dipakai blackbox exporter
  GET  /metrics    format Prometheus
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from model import DRIFT_POOL, LABELS, NORMAL_POOL, SentimentModel, oov_bins, psi, tokenize

MODEL_VERSION = os.getenv("MODEL_VERSION", "nb-1.0")
PORT = int(os.getenv("PORT", "8000"))
STATIC = Path(__file__).with_name("static")

model = SentimentModel.train()
REFERENCE_BINS = oov_bins([model.oov_ratio(text) for text, _ in NORMAL_POOL])
window: deque[float] = deque(maxlen=100)
window_lock = threading.Lock()

# ---- Layer 1: sistem -------------------------------------------------------
HTTP_REQUESTS = Counter("http_requests_total", "Jumlah request HTTP", ["method", "path", "status"])
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds", "Latensi request HTTP (detik)", ["path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.35, 0.5, 1.0, 2.0),
)
# ---- Layer 2: model --------------------------------------------------------
PREDICTIONS = Counter("model_predictions_total", "Jumlah prediksi per label", ["label"])
CONFIDENCE = Histogram(
    "model_confidence", "Probabilitas tertinggi tiap prediksi",
    buckets=(0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0),
)
OOV = Histogram(
    "model_input_oov_ratio", "Rasio kata input yang tidak ada di kosakata training",
    buckets=(0.05, 0.15, 0.3, 0.5, 1.0),
)
DRIFT_PSI = Gauge("model_input_drift_psi", "PSI rasio OOV: 100 request terakhir vs data referensi")
MODEL_INFO = Gauge("model_info", "Model yang sedang melayani", ["version", "algorithm"])
MODEL_INFO.labels(MODEL_VERSION, "multinomial-naive-bayes").set(1)
# ---- Layer 3: bisnis -------------------------------------------------------
FEEDBACK = Counter("model_feedback_total", "Umpan balik pengguna terhadap prediksi", ["verdict"])
# ---- Gangguan buatan untuk latihan alert -----------------------------------
CHAOS_DELAY = Gauge("chaos_delay_seconds", "Latensi tambahan buatan")
CHAOS_ERROR = Gauge("chaos_error_ratio", "Rasio error 500 buatan")
chaos = {"delay_s": 0.0, "error_ratio": 0.0}

app = FastAPI(title="Sentiment API - ML Monitoring", version=MODEL_VERSION)


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", "tidak-dikenal")
        if path != "/metrics":
            HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            HTTP_LATENCY.labels(path).observe(time.perf_counter() - started)


class PredictIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class FeedbackIn(BaseModel):
    predicted: Literal["positif", "negatif", "netral"]
    actual: Literal["positif", "negatif", "netral"]


class SimulateIn(BaseModel):
    mode: Literal["normal", "drift", "stop"]
    duration_s: int = Field(180, ge=10, le=1800)
    rps: float = Field(5, gt=0, le=20)


class ChaosIn(BaseModel):
    delay_ms: int = Field(0, ge=0, le=5000)
    error_ratio: float = Field(0, ge=0, le=1)


@app.get("/", include_in_schema=False)
def panel():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict")
def predict(body: PredictIn):
    if not tokenize(body.text):
        raise HTTPException(422, "Teks harus berisi minimal satu kata")
    if chaos["delay_s"]:
        time.sleep(chaos["delay_s"])
    if chaos["error_ratio"] and random.random() < chaos["error_ratio"]:
        raise HTTPException(500, "Error buatan dari chaos (simulasi)")

    probs = model.predict_proba(body.text)
    label = max(probs, key=probs.get)
    oov = model.oov_ratio(body.text)
    PREDICTIONS.labels(label).inc()
    CONFIDENCE.observe(probs[label])
    OOV.observe(oov)
    with window_lock:
        window.append(oov)
        if len(window) >= 30:
            DRIFT_PSI.set(psi(REFERENCE_BINS, oov_bins(window)))
    return {
        "label": label,
        "confidence": round(probs[label], 4),
        "probs": {k: round(v, 4) for k, v in probs.items()},
        "oov_ratio": round(oov, 3),
        "model_version": MODEL_VERSION,
    }


@app.post("/feedback")
def feedback(body: FeedbackIn):
    verdict = "benar" if body.predicted == body.actual else "salah"
    FEEDBACK.labels(verdict).inc()
    return {"verdict": verdict}


# ---- Simulator trafik (thread di dalam container) --------------------------
def _post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


class Simulator:
    def __init__(self):
        self.mode = "idle"
        self.sent = 0
        self.errors = 0
        self.ends_at = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, mode: str, duration_s: int, rps: float):
        self.stop()
        pool = NORMAL_POOL if mode == "normal" else DRIFT_POOL
        self._stop = threading.Event()
        self.mode, self.sent, self.errors = mode, 0, 0
        self.ends_at = time.time() + duration_s
        self._thread = threading.Thread(target=self._run, args=(pool, rps, self._stop), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self.mode = "idle"

    def _run(self, pool, rps: float, stop: threading.Event):
        base = f"http://127.0.0.1:{PORT}"
        while not stop.is_set() and time.time() < self.ends_at:
            text, actual = random.choice(pool)
            try:
                out = _post(f"{base}/predict", {"text": text})
                self.sent += 1
                if random.random() < 0.5:  # separuh pengguna memberi umpan balik
                    _post(f"{base}/feedback", {"predicted": out["label"], "actual": actual})
            except Exception:
                self.errors += 1
            stop.wait(1 / rps)
        if not stop.is_set():
            self.mode = "idle"

    def status(self) -> dict:
        left = max(0, round(self.ends_at - time.time())) if self.mode != "idle" else 0
        return {"mode": self.mode, "sent": self.sent, "errors": self.errors, "seconds_left": left}


simulator = Simulator()


@app.post("/simulate")
def simulate(body: SimulateIn):
    if body.mode == "stop":
        simulator.stop()
    else:
        simulator.start(body.mode, body.duration_s, body.rps)
    return simulator.status()


@app.get("/simulate")
def simulate_status():
    return simulator.status()


@app.post("/chaos")
def set_chaos(body: ChaosIn):
    chaos["delay_s"] = body.delay_ms / 1000
    chaos["error_ratio"] = body.error_ratio
    CHAOS_DELAY.set(chaos["delay_s"])
    CHAOS_ERROR.set(chaos["error_ratio"])
    return {"delay_ms": body.delay_ms, "error_ratio": body.error_ratio}


@app.get("/chaos")
def get_chaos():
    return {"delay_ms": int(chaos["delay_s"] * 1000), "error_ratio": chaos["error_ratio"]}


@app.get("/labels", include_in_schema=False)
def labels():
    return {"labels": list(LABELS)}
