"""Redis-based session management — 10-turn context + 30min TTL. (issue #46)"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from config.settings import Settings

logger = logging.getLogger(__name__)
_log = logging.getLogger("uvicorn.error")

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
            key = f"session:{sid}"
            self._redis.hset(key, mapping={"turns": json.dumps([]), "title": ""})
            self._redis.expire(key, _SESSION_TTL)
        except Exception as e:
            logger.warning("redis create session failed: %s", e)
        return sid

    def add_turn(self, session_id: str, user_text: str, assistant_text: str, sql: str | None = None) -> None:
        try:
            key = f"session:{session_id}"
            raw = self._redis.hget(key, "turns")
            turns = json.loads(raw) if raw else []
            turn = {"user": user_text[: _MAX_TURN_LENGTH], "assistant": assistant_text[: _MAX_TURN_LENGTH]}
            if sql:
                turn["sql"] = sql
            turns.append(turn)
            if len(turns) > _MAX_TURNS:
                turns = turns[-_MAX_TURNS:]
            # Auto-name session with first query if not yet named
            title = self._redis.hget(key, "title") or ""
            if not title and user_text:
                title = user_text[:50]
            self._redis.hset(key, mapping={"turns": json.dumps(turns), "title": title})
            self._redis.expire(key, _SESSION_TTL)
        except Exception as e:
            logger.warning("redis add turn failed: %s", e)

    def list_sessions(self) -> list[dict[str, str]]:
        """Return all active sessions with id and title from Redis."""
        try:
            keys = list(self._redis.keys("session:*"))
            if not keys:
                return []
            pipe = self._redis.pipeline()
            for k in keys:
                pipe.hget(k, "title")
            titles = pipe.execute()
            result = []
            for k, title in zip(keys, titles):
                sid = k.removeprefix("session:") if isinstance(k, str) else k.decode().removeprefix("session:")
                t = title if isinstance(title, str) else (title.decode() if title else "")
                result.append({"session_id": sid, "title": t or sid[:8]})
            return result
        except Exception as e:
            logger.warning("redis list sessions failed: %s", e)
            return []

    def get_context(self, session_id: str) -> list[dict[str, str]]:
        try:
            raw = self._redis.hget(f"session:{session_id}", "turns")
            turns = json.loads(raw) if raw else []
            _log.info("[ctx] get_context sid=%s turns=%d raw_exists=%s",
                      session_id, len(turns), bool(raw))
            return turns
        except Exception as e:
            _log.warning("[ctx] get_context FAILED sid=%s err=%s", session_id, e)
            return []

    def end_session(self, session_id: str) -> None:
        try:
            pipe = self._redis.pipeline()
            pipe.delete(f"session:{session_id}")
            for k in self._redis.scan_iter(f"cache:{session_id}:*"):
                pipe.delete(k)
            pipe.execute()
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
