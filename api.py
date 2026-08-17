"""FastAPI service for wallet scoring, real alerts, collection, and training."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from risk_system import __version__
from risk_system.collector import CollectionSettings, WalletCollector
from risk_system.etherscan import configured_api_keys
from risk_system.live import AlertStore, LiveEventBroker, utc_now
from risk_system.reputation import sync_etherscan_gas_guzzler_labels
from risk_system.training import (
    ModelTrainer,
    TrainingOptions,
    list_model_versions,
    rollback_model,
)
from wallet_check import clear_model_cache, score_wallet_data

load_dotenv(Path(__file__).resolve().parent / ".env")

try:
    from pythonjsonlogger.json import JsonFormatter as _JsonFormatterClass

    JsonFormatterClass: Any = _JsonFormatterClass
except ImportError:
    JsonFormatterClass = None

try:
    import redis as _redis_module

    redis_module: Any = _redis_module
except ImportError:
    redis_module = None


def configure_logging() -> None:
    handler = logging.StreamHandler()
    if JsonFormatterClass:
        handler.setFormatter(JsonFormatterClass("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


configure_logging()
logger = logging.getLogger("risk_api")


REQUESTS = Counter("risk_api_requests_total", "API requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("risk_api_request_seconds", "Total request latency", ["path"])
INFERENCE_LATENCY = Histogram("risk_model_inference_seconds", "Wallet model inference latency", ["token"])
CACHE_HITS = Counter("risk_cache_hits_total", "Wallet score cache hits", ["backend"])


class WalletScoringRequest(BaseModel):
    address: str = Field(..., pattern=r"^0x[a-fA-F0-9]{40}$")
    manual_token: str | None = None
    debug: bool = False


class BatchScoringRequest(BaseModel):
    addresses: list[str] = Field(..., min_length=1, max_length=250)
    manual_token: str | None = None


class CollectionRequest(BaseModel):
    target_wallets: int = Field(1000, ge=1, le=1_000_000)
    tokens: list[str] = Field(default_factory=lambda: ["USDT", "USDC"])
    seed_wallets: list[str] = Field(default_factory=list, max_length=1000)
    max_neighbors_per_wallet: int = Field(25, ge=1, le=500)
    transactions_per_wallet: int = Field(100, ge=1, le=1000)
    resume: bool = True


class TrainingRequest(BaseModel):
    token: str = "usdt"
    model: str = "auto"
    estimators: int = Field(300, ge=50, le=5000)
    max_depth: int | None = Field(16, ge=2, le=128)
    cv_folds: int = Field(5, ge=2, le=10)
    tuning_trials: int = Field(0, ge=0, le=200)


class RollbackRequest(BaseModel):
    token: str
    version: str


class CaseUpdateRequest(BaseModel):
    status: str
    assignee: str | None = Field(None, max_length=120)
    note: str | None = Field(None, max_length=4000)


class TTLCache:
    def __init__(self) -> None:
        self.ttl = int(os.getenv("SCORE_CACHE_TTL_SECONDS", "120"))
        self.memory: dict[str, tuple[float, str]] = {}
        self.lock = threading.Lock()
        self.redis_client = None
        redis_url = os.getenv("REDIS_URL", "").strip()
        if redis_url and redis_module:
            try:
                self.redis_client = redis_module.Redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
            except Exception as exc:
                logger.warning("Redis unavailable; using local TTL cache", extra={"error": str(exc)})
                self.redis_client = None

    @property
    def backend(self) -> str:
        return "redis" if self.redis_client else "memory"

    def get(self, key: str) -> dict[str, Any] | None:
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    CACHE_HITS.labels("redis").inc()
                    return json.loads(value)
            except Exception:
                pass
        with self.lock:
            item = self.memory.get(key)
            if item and item[0] > time.monotonic():
                CACHE_HITS.labels("memory").inc()
                return json.loads(item[1])
            if item:
                self.memory.pop(key, None)
        return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        serialized = json.dumps(value, default=str)
        if self.redis_client:
            try:
                self.redis_client.setex(key, self.ttl, serialized)
            except Exception:
                pass
        with self.lock:
            self.memory[key] = (time.monotonic() + self.ttl, serialized)


class JobRegistry:
    """Persist background job snapshots and cancellation handles."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.root = Path("data/jobs")
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / f"{kind}.json"
        self.records: dict[str, dict[str, Any]] = {}
        self.cancel_events: dict[str, threading.Event] = {}
        self.lock = threading.Lock()
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                self.records = {
                    item["job_id"] if "job_id" in item else item["run_id"]: item for item in stored
                }
                for record in self.records.values():
                    if record.get("status") in {"queued", "running"}:
                        record["status"] = "interrupted"
                        record["message"] = "API restarted; resume or start the job again"
            except (OSError, ValueError, json.JSONDecodeError):
                self.records = {}

    def save(self, record: dict[str, Any]) -> None:
        identifier = str(record.get("job_id") or record.get("run_id"))
        with self.lock:
            self.records[identifier] = record
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(list(self.records.values()), indent=2, default=str), encoding="utf-8"
            )
            temporary.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        return sorted(
            self.records.values(),
            key=lambda item: str(item.get("updated_at") or item.get("started_at") or ""),
            reverse=True,
        )

    def get(self, identifier: str) -> dict[str, Any]:
        if identifier not in self.records:
            raise KeyError(identifier)
        return self.records[identifier]

    def cancel(self, identifier: str) -> dict[str, Any]:
        event = self.cancel_events.get(identifier)
        if event is None:
            raise KeyError(identifier)
        event.set()
        return self.get(identifier)


cache = TTLCache()
alert_store = AlertStore()
collection_jobs = JobRegistry("collections")
training_jobs = JobRegistry("training")


def score_live_wallet(wallet: str, token: str) -> dict[str, Any]:
    return score_wallet_data(wallet, manual_token=token)


live_broker = LiveEventBroker(alert_store, scorer=score_live_wallet)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await live_broker.start()
    yield
    await live_broker.stop()


app = FastAPI(
    title="Stablecoin Payout Risk API",
    description="Wallet risk scoring, real chain alerts, data collection, and local model training",
    version=__version__,
    lifespan=lifespan,
)

cors_origins = [
    value.strip()
    for value in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


rate_windows: dict[str, deque[float]] = defaultdict(deque)
rate_lock = threading.Lock()


@app.middleware("http")
async def request_controls(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    rate_limit_localhost = os.getenv("RATE_LIMIT_LOCALHOST", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    is_loopback = client in {"127.0.0.1", "::1", "testclient"}
    if request.url.path not in {"/metrics", "/health"} and (rate_limit_localhost or not is_loopback):
        per_minute = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))
        now = time.monotonic()
        with rate_lock:
            window = rate_windows[client]
            while window and window[0] < now - 60:
                window.popleft()
            if len(window) >= per_minute:
                REQUESTS.labels(request.method, request.url.path, "429").inc()
                return JSONResponse(
                    status_code=429,
                    content={"error": {"code": "RATE_LIMITED", "message": "Request limit exceeded"}},
                    headers={"Retry-After": "60"},
                )
            window.append(now)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        REQUESTS.labels(request.method, request.url.path, "500").inc()
        REQUEST_LATENCY.labels(request.url.path).observe(time.perf_counter() - started)
        raise
    REQUESTS.labels(request.method, request.url.path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.url.path).observe(time.perf_counter() - started)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


def _api_key_hashes() -> list[str]:
    return [value.strip().lower() for value in os.getenv("API_KEYS_SHA256", "").split(",") if value.strip()]


def _valid_api_key(value: str | None) -> bool:
    hashes = _api_key_hashes()
    if not hashes:
        return os.getenv("REQUIRE_API_AUTH", "false").lower() not in {"1", "true", "yes", "on"}
    if not value:
        return False
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return any(hmac.compare_digest(digest, expected) for expected in hashes)


def require_api_key(x_api_key: str | None = Header(None)) -> None:
    if not _valid_api_key(x_api_key):
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "A valid X-API-Key header is required"},
        )


def require_local_operation(_: None = Depends(require_api_key)) -> None:
    enabled = os.getenv("ENABLE_LOCAL_TRAINING", "false").lower() in {"1", "true", "yes", "on"}
    hosted = os.getenv("NETLIFY", "false").lower() in {"1", "true", "yes", "on"}
    if not enabled or hosted:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "LOCAL_OPERATION_DISABLED",
                "message": "Collection and training require a local API with ENABLE_LOCAL_TRAINING=true",
            },
        )


def _score(request: WalletScoringRequest) -> dict[str, Any]:
    token = request.manual_token.upper() if request.manual_token else "auto"
    cache_key = f"score:{request.address.lower()}:{token}"
    cached = cache.get(cache_key)
    if cached:
        return {**cached, "cache_hit": True}
    with INFERENCE_LATENCY.labels(token).time():
        result = score_wallet_data(
            request.address,
            manual_token=request.manual_token,
            debug=request.debug,
        )
    result.update(timestamp=utc_now(), cache_hit=False)
    features = result.get("features") or {}
    result.update(
        graph_degree=int(features.get("graph_degree", 0)),
        graph_pagerank=float(features.get("graph_pagerank", 0.0)),
        connected_to_malicious=int(features.get("connected_to_malicious", 0)),
        features_extracted=bool(features),
    )
    cache.set(cache_key, result)
    event = {
        "event_id": f"manual-{uuid.uuid4().hex}",
        "timestamp": result["timestamp"],
        "wallet": result["wallet"],
        "token": result.get("token"),
        "decision": result["decision"],
        "score": result.get("score"),
        "reason": result.get("reason"),
        "source": "manual",
        "verified_real": result.get("data_status") in {"MODEL_SCORED", "REPUTATION_MATCH"},
        "assessment_status": result.get("assessment_status"),
        "data_status": result.get("data_status"),
    }
    alert_store.add_event(event)
    return result


@app.get("/health", tags=["System"])
def health() -> dict[str, Any]:
    model_versions = list_model_versions()
    try:
        import db

        durable = db.health_status()
    except Exception:
        durable = {"database": "error", "redis": "error"}
    return {
        "status": "healthy" if live_broker.status["state"] not in {"error"} else "degraded",
        "timestamp": utc_now(),
        "version": __version__,
        "database": durable["database"],
        "redis_feature_cache": durable["redis"],
        "cache": cache.backend,
        "etherscan_keys_configured": len(configured_api_keys()),
        "live_stream": dict(live_broker.status),
        "active_models": model_versions["active"],
        "local_training_enabled": os.getenv("ENABLE_LOCAL_TRAINING", "false").lower()
        in {"1", "true", "yes", "on"},
        "api_auth_enabled": bool(_api_key_hashes()),
    }


@app.get("/metrics", tags=["System"])
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/model_info", tags=["Models"])
@app.get("/get_model_info", tags=["Models"], include_in_schema=False)
def model_info(_: None = Depends(require_api_key)) -> dict[str, Any]:
    versions = list_model_versions()
    return {
        "trained_tokens": sorted(versions["active"]),
        "supported_tokens": ["USDT", "USDC", "BUSD", "DAI", "USDP", "TUSD"],
        "supported_all_tokens": 54,
        "active_versions": versions["active"],
        "versions": versions["versions"],
        "api_version": __version__,
    }


@app.post("/score_wallet", tags=["Scoring"])
def score_wallet_endpoint(
    request: WalletScoringRequest, _: None = Depends(require_api_key)
) -> dict[str, Any]:
    return _score(request)


@app.post("/batch_score", tags=["Scoring"])
def batch_score(request: BatchScoringRequest, _: None = Depends(require_api_key)) -> dict[str, Any]:
    started = time.perf_counter()
    results = []
    for address in request.addresses:
        try:
            results.append(_score(WalletScoringRequest(address=address, manual_token=request.manual_token)))
        except Exception as exc:
            results.append({"wallet": address, "decision": "ERROR", "reason": str(exc)})
    return {
        "total_requested": len(request.addresses),
        "total_scored": sum(item.get("decision") != "ERROR" for item in results),
        "results": results,
        "batch_time_ms": (time.perf_counter() - started) * 1000,
    }


@app.get("/live/status", tags=["Live"])
def live_status(_: None = Depends(require_api_key)) -> dict[str, Any]:
    return dict(live_broker.status)


@app.get("/alerts", tags=["Alerts"])
def alerts(
    limit: int = Query(100, ge=1, le=1000),
    decision: str | None = None,
    _: None = Depends(require_api_key),
) -> list[dict[str, Any]]:
    return alert_store.recent_events(limit=limit, decision=decision)


@app.get("/alerts/statistics", tags=["Alerts"])
def alert_statistics(_: None = Depends(require_api_key)) -> dict[str, Any]:
    return alert_store.statistics()


@app.get("/cases", tags=["Cases"])
def cases(
    limit: int = Query(100, ge=1, le=1000),
    status: str | None = None,
    _: None = Depends(require_api_key),
) -> list[dict[str, Any]]:
    return alert_store.cases(limit=limit, status=status)


@app.patch("/cases/{case_id}", tags=["Cases"])
def update_case(
    case_id: str, request: CaseUpdateRequest, _: None = Depends(require_api_key)
) -> dict[str, Any]:
    try:
        return alert_store.update_case(case_id, request.status, request.assignee, request.note)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "CASE_NOT_FOUND", "message": case_id}) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_CASE", "message": str(exc)}) from exc


@app.get("/graph", tags=["Graph"])
def graph(limit: int = Query(250, ge=10, le=1000), _: None = Depends(require_api_key)) -> dict[str, Any]:
    events = alert_store.recent_events(limit=limit)
    node_map: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for event in events:
        target = event.get("wallet")
        source = event.get("from_wallet")
        if target:
            node_map[target] = {
                "id": target,
                "token": event.get("token"),
                "decision": event.get("decision"),
                "score": event.get("score"),
            }
        if source:
            node_map.setdefault(source, {"id": source, "token": event.get("token"), "decision": "OBSERVED"})
            edges.append({"source": source, "target": target, "tx_hash": event.get("tx_hash")})
    return {"nodes": list(node_map.values()), "edges": edges, "source": "persisted real transfer events"}


@app.post("/threat-intel/sync/etherscan-gas-guzzlers", tags=["Threat Intelligence"])
def sync_gas_guzzler_threat_intel(_: None = Depends(require_local_operation)) -> dict[str, Any]:
    try:
        return sync_etherscan_gas_guzzler_labels()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "THREAT_INTEL_SYNC_FAILED", "message": str(exc)},
        ) from exc


def _collection_worker(job_id: str, settings: CollectionSettings, cancel_event: threading.Event) -> None:
    def progress(state):
        collection_jobs.save({**state.__dict__, "updated_at": utc_now()})

    try:
        collector = WalletCollector(
            settings,
            job_id=job_id,
            progress=progress,
            cancel_event=cancel_event,
        )
        state = collector.run()
        progress(state)
    except Exception as exc:
        collection_jobs.save(
            {
                "job_id": job_id,
                "status": "failed",
                "settings": settings.__dict__,
                "message": str(exc),
                "updated_at": utc_now(),
                "finished_at": utc_now(),
            }
        )


@app.post("/collection/start", tags=["Collection"])
def start_collection(
    request: CollectionRequest, _: None = Depends(require_local_operation)
) -> dict[str, Any]:
    settings = CollectionSettings(**request.model_dump())
    settings.validate()
    job_id = uuid.uuid4().hex[:12]
    record = {
        "job_id": job_id,
        "status": "queued",
        "settings": request.model_dump(),
        "discovered": 0,
        "processed": 0,
        "requests": 0,
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "message": "Collection queued",
    }
    cancel_event = threading.Event()
    collection_jobs.cancel_events[job_id] = cancel_event
    collection_jobs.save(record)
    threading.Thread(
        target=_collection_worker,
        args=(job_id, settings, cancel_event),
        name=f"collection-{job_id}",
        daemon=True,
    ).start()
    return record


@app.get("/collection/jobs", tags=["Collection"])
def list_collection_jobs(_: None = Depends(require_api_key)) -> list[dict[str, Any]]:
    return collection_jobs.list()


@app.get("/collection/status/{job_id}", tags=["Collection"])
def collection_status(job_id: str, _: None = Depends(require_api_key)) -> dict[str, Any]:
    try:
        return collection_jobs.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": job_id}) from None


@app.post("/collection/cancel/{job_id}", tags=["Collection"])
def cancel_collection(job_id: str, _: None = Depends(require_local_operation)) -> dict[str, Any]:
    try:
        return collection_jobs.cancel(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_RUNNING", "message": job_id}) from None


def _training_worker(run_id: str, options: TrainingOptions, cancel_event: threading.Event) -> None:
    def progress(run):
        training_jobs.save({**run.__dict__, "updated_at": utc_now()})

    trainer = ModelTrainer(options, run_id=run_id, progress=progress, cancel_event=cancel_event)
    result = trainer.execute()
    clear_model_cache()
    progress(result)


@app.post("/training/train", tags=["Training"])
def start_training(request: TrainingRequest, _: None = Depends(require_local_operation)) -> dict[str, Any]:
    options = TrainingOptions(**request.model_dump())
    options.validate()
    run_id = uuid.uuid4().hex[:12]
    record = {
        "run_id": run_id,
        "status": "queued",
        "token": options.token,
        "model": options.model,
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "progress": 0.0,
        "stage": "queued",
        "metrics": {},
        "versions": {},
        "message": "Training queued",
    }
    cancel_event = threading.Event()
    training_jobs.cancel_events[run_id] = cancel_event
    training_jobs.save(record)
    threading.Thread(
        target=_training_worker,
        args=(run_id, options, cancel_event),
        name=f"training-{run_id}",
        daemon=True,
    ).start()
    return record


@app.get("/training/history", tags=["Training"])
def training_history(_: None = Depends(require_api_key)) -> list[dict[str, Any]]:
    return training_jobs.list()


@app.get("/training/status/{run_id}", tags=["Training"])
def training_status(run_id: str, _: None = Depends(require_api_key)) -> dict[str, Any]:
    try:
        return training_jobs.get(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": run_id}) from None


@app.post("/training/cancel/{run_id}", tags=["Training"])
def cancel_training(run_id: str, _: None = Depends(require_local_operation)) -> dict[str, Any]:
    try:
        return training_jobs.cancel(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_RUNNING", "message": run_id}) from None


@app.get("/training/versions", tags=["Training"])
def training_versions(_: None = Depends(require_api_key)) -> dict[str, Any]:
    return list_model_versions()


@app.post("/training/rollback", tags=["Training"])
def training_rollback(request: RollbackRequest, _: None = Depends(require_local_operation)) -> dict[str, Any]:
    try:
        result = rollback_model(request.token, request.version)
        clear_model_cache(request.token)
        return result
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail={"code": "ROLLBACK_FAILED", "message": str(exc)}) from exc


@app.post("/training/rollback/{run_id}", tags=["Training"], include_in_schema=False)
def rollback_run(run_id: str, _: None = Depends(require_local_operation)) -> dict[str, Any]:
    try:
        record = training_jobs.get(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": run_id}) from None
    versions = record.get("versions") or {}
    if not versions:
        raise HTTPException(
            status_code=400, detail={"code": "NO_VERSION", "message": "Run produced no model version"}
        )
    results = []
    for token, version in versions.items():
        results.append(rollback_model(token, version))
        clear_model_cache(token)
    return {"run_id": run_id, "restored": results}


@app.websocket("/ws/live-alerts")
async def websocket_live_alerts(websocket: WebSocket, api_key: str | None = Query(None)):
    if not _valid_api_key(api_key or websocket.headers.get("x-api-key")):
        await websocket.close(code=4401, reason="Authentication required")
        return
    await websocket.accept()
    queue = live_broker.subscribe()
    try:
        await websocket.send_json(
            {"type": "status", "live": dict(live_broker.status), "timestamp": utc_now()}
        )
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json({"type": "event", **event})
            except TimeoutError:
                await websocket.send_json(
                    {"type": "status", "live": dict(live_broker.status), "timestamp": utc_now()}
                )
    except WebSocketDisconnect:
        pass
    finally:
        live_broker.unsubscribe(queue)
