"""
Kafka consumer that processes emission events in the background.

Runs as a long-lived daemon thread started at app startup. For every
emission.created event it invalidates the Redis summary cache and,
when the anomaly model is available, scores the record and publishes
an alert if it looks anomalous.
"""
import json
import logging

from app.core.cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmissionEventConsumer:
    """Long-lived Kafka consumer with graceful degradation."""

    def __init__(self):
        self.running = False
        self._consumer = None

    def _get_consumer(self):
        """
        Create a KafkaConsumer subscribed to the emission topic.
        Returns None if Kafka is not available (graceful degradation).
        """
        if not settings.KAFKA_BOOTSTRAP_SERVERS:
            return None
        try:
            from kafka import KafkaConsumer

            consumer = KafkaConsumer(
                settings.KAFKA_EMISSION_TOPIC,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id="carbonsense-processor",
                auto_offset_reset="latest",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                # Wake up the poll loop regularly so stop() is honoured
                consumer_timeout_ms=1000,
            )
            logger.info(
                f"Kafka consumer subscribed to '{settings.KAFKA_EMISSION_TOPIC}' "
                f"on {settings.KAFKA_BOOTSTRAP_SERVERS}"
            )
            return consumer
        except Exception as e:  # kafka-python missing or broker down
            logger.warning(f"Kafka consumer unavailable: {e}")
            return None

    def process_message(self, message: dict) -> None:
        """
        Process a single emission event.
        For emission.created: invalidate the summary cache and score
        the record for anomalies if a model is loaded.
        """
        event_type = message.get("event_type")
        payload = message.get("payload", {})

        if event_type != "emission.created":
            return

        company_id = payload.get("company_id")
        if company_id:
            invalidated = cache.delete_pattern(f"summary:company:{company_id}:*")
            logger.debug(
                f"Invalidated {invalidated} summary cache keys for company {company_id}"
            )

        self._score_record(payload)

    def _score_record(self, payload: dict) -> None:
        """Score a new record with the anomaly detector, alert if anomalous."""
        from app.ml.model_registry import load_model, model_exists

        if not model_exists("anomaly_detector"):
            return

        try:
            import pandas as pd

            from app.data_pipeline.kafka_producer import emission_producer
            from app.db.database import SessionLocal
            from app.ml.anomaly_detector import build_anomaly_features
            from app.ml.feature_engineering import load_emission_dataframe

            bundle = load_model("anomaly_detector")["model"]
            model, scaler = bundle["model"], bundle["scaler"]

            db = SessionLocal()
            try:
                df = load_emission_dataframe(db, company_id=payload.get("company_id"))
            finally:
                db.close()
            if df.empty:
                return

            df_features = build_anomaly_features(df)
            record_id = payload.get("id")
            row = df_features[df_features["id"] == record_id]
            if row.empty:
                return

            feature_cols = ["co2_tonnes", "z_score", "ratio_to_median",
                            "mom_change", "reporting_month"]
            X = scaler.transform(row[feature_cols].fillna(0))
            if model.predict(X)[0] == -1:
                score = float(model.decision_function(X)[0])
                logger.info(
                    f"Anomaly detected on ingestion — record {record_id}, score {score:.4f}"
                )
                emission_producer.publish_anomaly_alert(
                    record_id=record_id,
                    company_id=payload.get("company_id"),
                    score=score,
                )
        except Exception as e:  # noqa: BLE001 — scoring failure must not kill the loop
            logger.warning(f"Anomaly scoring in consumer failed: {e}")

    def start(self) -> None:
        """
        Consume messages until stop() is called.
        Intended to run inside a daemon thread — never crashes the thread.
        """
        self._consumer = self._get_consumer()
        if self._consumer is None:
            logger.info("Kafka consumer not started — broker unavailable")
            return

        self.running = True
        logger.info("Kafka consumer loop started")

        while self.running:
            try:
                # consumer_timeout_ms makes iteration end after idle periods
                for message in self._consumer:
                    if not self.running:
                        break
                    logger.debug(f"Kafka message received: {message.value}")
                    self.process_message(message.value)
            except StopIteration:
                continue  # idle timeout — loop again to check self.running
            except Exception as e:  # noqa: BLE001 — keep the thread alive
                logger.error(f"Kafka consumer error (continuing): {e}")

        try:
            self._consumer.close()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Kafka consumer close failed: {e}")
        logger.info("Kafka consumer stopped")

    def stop(self) -> None:
        """Gracefully stop the consumer loop."""
        self.running = False


emission_consumer = EmissionEventConsumer()  # module singleton
