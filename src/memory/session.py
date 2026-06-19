"""Redis-based session management — 10-turn context + 30min TTL. (issue #46)"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from config.settings import Settings

logger = logging.getLogger(__name__)

_SESSION_TTL = 30 * 60  # 30 minutes
_MAX_TURNS = 10
_MAX_TURN_LENGTH = 500  # characters per turn


class SessionManager:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._client: Any = None

    @property
    def _redis(self):
        if self._client is None:
            import redis
            s = self._settings
            self._client = redis.Redis(host=s.redis_host, port=s.redis_port, password=s.redis_password or None, db=s.redis_db, decode_responses=True)
        return self._client

    def create_session(self) -> str:
        sid = str(uuid.uuid4())
        try:
            self._redis.hset(f"session:{sid}", "turns", json.dumps([]))
            self._redis.expire(f"session:{sid}", _SESSION_TTL)
        except Exception as e:
            logger.warning("redis create session failed: %s", e)
        return sid

    def add_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        try:
            key = f"session:{session_id}"
            raw = self._redis.hget(key, "turns")
            turns = json.loads(raw) if raw else []
            turns.append({"user": user_text[: _MAX_TURN_LENGTH], "assistant": assistant_text[: _MAX_TURN_LENGTH]})
            if len(turns) > _MAX_TURNS:
                turns = turns[-_MAX_TURNS:]
            self._redis.hset(key, "turns", json.dumps(turns))
            self._redis.expire(key, _SESSION_TTL)
        except Exception as e:
            logger.warning("redis add turn failed: %s", e)

    def get_context(self, session_id: str) -> list[dict[str, str]]:
        try:
            raw = self._redis.hget(f"session:{session_id}", "turns")
            return json.loads(raw) if raw else []
        except Exception:
            return []

    def end_session(self, session_id: str) -> None:
        try:
            self._redis.delete(f"session:{session_id}", f"cache:{session_id}:*")
        except Exception as e:
            logger.warning("redis end session failed: %s", e)


class ResultCache:
    def __init__(self, settings: Settings | None = None):
        self._settings = settings or Settings()
        self._client: Any = None

    @property
    def _redis(self):
        if self._client is None:
            import redis
            s = self._settings
            self._client = redis.Redis(host=s.redis_host, port=s.redis_port, password=s.redis_password or None, db=s.redis_db, decode_responses=True)
        return self._client

    def get(self, session_id: str, query_hash: str) -> str | None:
        try:
            return self._redis.get(f"cache:{session_id}:{query_hash}")
        except Exception:
            return None

    def set(self, session_id: str, query_hash: str, result: str, ttl: int = 300) -> None:
        try:
            self._redis.setex(f"cache:{session_id}:{query_hash}", ttl, result)
        except Exception as e:
            logger.warning("redis cache set failed: %s", e)
