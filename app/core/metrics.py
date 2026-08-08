"""
Custom Prometheus metrics for CarbonSense.

These expose business-level insights, not just infrastructure metrics.
Infrastructure metrics (CPU, memory) come from node_exporter automatically.

Every increment in application code is wrapped in try/except — a metrics
failure must never affect the actual request.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)


emissions_ingested_total = Counter(
    "carbonsense_emissions_ingested_total",
    "Total emission records ingested",
    ["scope", "company_id"],
)

anomalies_detected_total = Counter(
    "carbonsense_anomalies_detected_total",
    "Total anomalous emission records detected",
    ["severity", "scope"],
)

csrd_reports_generated_total = Counter(
    "carbonsense_csrd_reports_generated_total",
    "Total CSRD reports generated",
    ["company_id"],
)

prediction_latency_seconds = Histogram(
    "carbonsense_prediction_latency_seconds",
    "ML prediction endpoint latency",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

active_websocket_connections = Gauge(
    "carbonsense_active_websocket_connections",
    "Number of active WebSocket connections",
)

model_drift_score = Gauge(
    "carbonsense_model_drift_score",
    "Current model drift score (0=no drift, 1=significant drift)",
    ["model_name"],
)

cache_hit_total = Counter(
    "carbonsense_cache_hit_total",
    "Redis cache hits",
    ["cache_key_type"],
)

cache_miss_total = Counter(
    "carbonsense_cache_miss_total",
    "Redis cache misses",
    ["cache_key_type"],
)


metrics_router = APIRouter(tags=["Observability"])


@metrics_router.get("/metrics")
def prometheus_metrics():
    """
    Prometheus scrape endpoint.
    Prometheus is configured to call this every 15 seconds.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
