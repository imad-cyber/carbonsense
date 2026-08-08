import json
import logging
from typing import Any
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheClient:
    """
    Wrapper around the Redis client.

    Why wrap it instead of using Redis directly everywhere?
    - Centralises error handling (Redis going down shouldn't crash the app)
    - Makes it easy to swap Redis for another cache later
    - Adds serialisation/deserialisation in one place
    - Makes mocking in tests trivial
    """

    def __init__(self):
        self._client: Redis | None = None

    def _get_client(self) -> Redis:
        """
        Lazy initialisation — only connect when first used.
        decode_responses=True means Redis returns strings, not bytes.
        """
        if self._client is None:
            self._client = Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,   # fail fast if Redis is down
                socket_timeout=2,
            )
        return self._client

    def get(self, key: str) -> Any | None:
        """
        Retrieve a cached value.
        Returns None on cache miss OR on Redis errors.
        Your app continues working even if Redis is down — this is
        called 'graceful degradation' and it's required in enterprise systems.
        """
        try:
            client = self._get_client()
            raw = client.get(key)
            if raw is None:
                self._record_metric(key, hit=False)
                return None
            self._record_metric(key, hit=True)
            return json.loads(raw)
        except RedisError as e:
            logger.warning(f"Redis GET failed for key '{key}': {e}")
            return None

    @staticmethod
    def _record_metric(key: str, hit: bool) -> None:
        """Prometheus cache metrics — failures must never affect the request."""
        try:
            from app.core.metrics import cache_hit_total, cache_miss_total
            key_type = key.split(":", 1)[0] or "unknown"
            if hit:
                cache_hit_total.labels(cache_key_type=key_type).inc()
            else:
                cache_miss_total.labels(cache_key_type=key_type).inc()
        except Exception:  # noqa: BLE001
            pass

    def set(self, key: str, value: Any, ttl: int) -> bool:
        """
        Store a value with an expiry time (TTL = Time To Live).
        After `ttl` seconds Redis automatically deletes the key.
        Returns True on success, False on failure.
        """
        try:
            client = self._get_client()
            serialised = json.dumps(value, default=str)
            # EX sets the TTL in seconds
            client.set(key, serialised, ex=ttl)
            return True
        except RedisError as e:
            logger.warning(f"Redis SET failed for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """Explicitly remove a cached value — used for cache invalidation."""
        try:
            client = self._get_client()
            client.delete(key)
            return True
        except RedisError as e:
            logger.warning(f"Redis DELETE failed for key '{key}': {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.
        Example: delete_pattern("summary:company:5:*")
        deletes all cached summaries for company 5 across all years.
        Returns count of deleted keys.
        """
        try:
            client = self._get_client()
            keys = client.keys(pattern)
            if keys:
                return client.delete(*keys)
            return 0
        except RedisError as e:
            logger.warning(f"Redis pattern delete failed for '{pattern}': {e}")
            return 0

    def ping(self) -> bool:
        """Health check — used in the /health endpoint."""
        try:
            return self._get_client().ping()
        except RedisError:
            return False


# Module-level singleton — one client instance shared across the app
cache = CacheClient()


# ── Cache key builders ──────────────────────────────────────────────────────
# Centralising key names here means you never have a typo mismatch
# between the code that sets a cache value and the code that reads it.

def make_summary_key(company_id: int, year: int) -> str:
    return f"summary:company:{company_id}:year:{year}"


def make_company_list_key(page: int, page_size: int) -> str:
    return f"companies:list:page:{page}:size:{page_size}"


def make_company_key(company_id: int) -> str:
    return f"company:{company_id}"