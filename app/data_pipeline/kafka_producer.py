"""
Kafka producer for real-time emission events.

Called when emission records are created or updated. Kafka being down
must NEVER fail an HTTP request — every publish returns False on
failure instead of raising.
"""
import json
import logging
from datetime import datetime, timezone

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmissionEventProducer:
    """
    Kafka producer for real-time emission events.
    Lazily connects on first publish; degrades gracefully when the
    broker is unreachable.
    """

    def __init__(self):
        self._producer = None
        self._unavailable = False  # remembered so we don't retry on every request

    def _get_producer(self):
        """
        Lazy-initialise the KafkaProducer.
        Returns None when Kafka is not configured or unreachable.
        """
        if not settings.KAFKA_BOOTSTRAP_SERVERS or self._unavailable:
            return None
        if self._producer is not None:
            return self._producer

        try:
            from kafka import KafkaProducer

            self._producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                # Fail fast — don't hold up HTTP requests waiting for a broker
                max_block_ms=2000,
                request_timeout_ms=5000,
            )
            logger.info(f"Kafka producer connected to {settings.KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:  # kafka-python missing or broker down
            logger.warning(f"Kafka unavailable — events will not be published: {e}")
            self._unavailable = True
            self._producer = None
        return self._producer

    def _publish(self, topic: str, event: dict) -> bool:
        producer = self._get_producer()
        if producer is None:
            return False
        try:
            producer.send(topic, value=event)
            return True
        except Exception as e:  # noqa: BLE001 — never propagate Kafka failures
            logger.warning(f"Kafka publish to '{topic}' failed: {e}")
            return False

    def publish_emission_created(self, record_data: dict) -> bool:
        """
        Publish an emission.created event.
        Returns True on success, False on failure (never raises).
        """
        event = {
            "event_type": "emission.created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": record_data,
        }
        return self._publish(settings.KAFKA_EMISSION_TOPIC, event)

    def publish_anomaly_alert(self, record_id: int, company_id: int, score: float) -> bool:
        """Publish an anomaly alert when an anomalous record is detected."""
        event = {
            "event_type": "emission.anomaly_detected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "record_id": record_id,
                "company_id": company_id,
                "anomaly_score": score,
            },
        }
        return self._publish(settings.KAFKA_ALERT_TOPIC, event)

    def close(self):
        """Flush and close the producer."""
        if self._producer is not None:
            try:
                self._producer.flush(timeout=5)
                self._producer.close(timeout=5)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Kafka producer close failed: {e}")
            finally:
                self._producer = None


emission_producer = EmissionEventProducer()  # module singleton
