"""Tests for session management + cache (#46)."""

import pytest
from memory.session import SessionManager, ResultCache


class TestSessionManager:
    def test_create_returns_uuid(self):
        sm = SessionManager()
        sid = sm.create_session()
        assert len(sid) == 36  # UUID format
        assert sm.get_context(sid) == []

    def test_add_and_get_turns(self):
        sm = SessionManager()
        sid = sm.create_session()
        sm.add_turn(sid, "hello", "hi there")
        ctx = sm.get_context(sid)
        assert len(ctx) == 1
        assert ctx[0]["user"] == "hello"

    def test_truncates_turns(self):
        sm = SessionManager()
        sid = sm.create_session()
        for i in range(12):
            sm.add_turn(sid, f"q{i}", f"a{i}")
        ctx = sm.get_context(sid)
        assert len(ctx) == 10  # capped at 10


class TestResultCache:
    def test_set_and_get(self):
        rc = ResultCache()
        rc.set("s1", "abc", '{"r":1}')
        assert rc.get("s1", "abc") == '{"r":1}'

    def test_miss_returns_none(self):
        rc = ResultCache()
        assert rc.get("s1", "nonexistent") is None
