import functools
import hashlib
import json

from redis import Redis
from redis.exceptions import RedisError

from app.config import CELERY_BROKER_URL

_client = None


def _get_client() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(CELERY_BROKER_URL, socket_connect_timeout=1, socket_timeout=1)
    return _client


def _cache_key(prefix: str, query_string: str) -> str:
    return f"kvuno:{prefix}:{hashlib.md5(query_string.encode()).hexdigest()}"


def api_cache(prefix: str, ttl: int = 300):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import request
            key = _cache_key(prefix, request.query_string.decode())
            try:
                client = _get_client()
                cached = client.get(key)
                if cached is not None:
                    return json.loads(cached)
            except RedisError:
                pass

            result = fn(*args, **kwargs)

            try:
                client = _get_client()
                client.setex(key, ttl, json.dumps(result, default=str))
            except RedisError:
                pass
            return result
        return wrapper
    return decorator


def invalidate_cache(prefix: str = None):
    """Delete all cache keys matching the given prefix (or all kvuno cache)."""
    pattern = f"kvuno:{prefix}:*" if prefix else "kvuno:*"
    try:
        client = _get_client()
        for key in client.scan_iter(match=pattern, count=100):
            client.delete(key)
    except RedisError:
        pass
