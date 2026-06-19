"""Time expression normalizer — relative/absolute/fixed-date periods. (issue #23)"""

from __future__ import annotations

import calendar
import logging
import re
from datetime import date, timedelta
from typing import Any

from normalizer.types import NormalizedValue

logger = logging.getLogger(__name__)

FIXED_DATE_PERIODS: dict[str, tuple[str, str]] = {
    "双十一": ("11-01", "11-11"),
    "618": ("06-01", "06-18"),
}


def _today() -> date:
    return date.today()


def _days_ago(n: int) -> tuple[date, date]:
    d = _today() - timedelta(days=n)
    return d, d


def _month_boundaries(year: int, month: int) -> tuple[date, date]:
    _, last = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last)


def _prev_month(today: date) -> tuple[date, date]:
    y, m = today.year, today.month - 1
    if m == 0:
        y -= 1
        m = 12
    return _month_boundaries(y, m)


def _quarter_bounds(today: date) -> tuple[date, date]:
    q = (today.month - 1) // 3
    start_month = q * 3 + 1
    end_month = start_month + 2
    return date(today.year, start_month, 1), date(
        today.year, end_month, calendar.monthrange(today.year, end_month)[1]
    )


# ---------------------------------------------------------------------------
# Parse entry point  (no field context needed)
# ---------------------------------------------------------------------------


def parse_time(raw_value: str) -> NormalizedValue:
    """Parse *raw_value* as a time expression.

    Returns ``NormalizedValue(value_type='time')``.  When the text cannot
    be parsed, ``need_confirm=True`` is set so Phase 6 can ask the user.
    """
    text = raw_value.strip()
    today = _today()

    # 1. relative time — atomic words
    start, end = _try_relative(text, today)
    if start:
        return _time_result(raw_value, start, end, "relative_time")

    # 2. fixed-date period  (双十一 / 618)
    start, end = _try_fixed(text, today)
    if start:
        return _time_result(raw_value, start, end, "fixed_period")

    # 3. absolute time — structured date strings
    abs_val = _try_absolute(text)
    if abs_val is not None:
        if isinstance(abs_val, tuple):
            return _time_result(raw_value, abs_val[0], abs_val[1], "absolute_time")
        return NormalizedValue(
            original=raw_value,
            normalized=abs_val,
            value_type="time",
            db_representation=f"(date = '{abs_val.isoformat()}')",
            confidence=1.0,
            matched_by="absolute_time",
        )

    return NormalizedValue(
        original=raw_value, value_type="time", need_confirm=True
    )


def _time_result(
    original: str, start: date, end: date, matched_by: str
) -> NormalizedValue:
    return NormalizedValue(
        original=original,
        normalized=(start, end),
        value_type="time",
        db_representation=f"(date >= '{start.isoformat()}' AND date <= '{end.isoformat()}')",
        confidence=1.0,
        matched_by=matched_by,
    )


# ---------------------------------------------------------------------------
# Relative time
# ---------------------------------------------------------------------------


def _try_relative(text: str, today: date) -> tuple[date | None, date | None]:
    dow = today.weekday()  # Mon=0 .. Sun=6
    monday = today - timedelta(days=dow)
    sunday = monday + timedelta(days=6)

    if text == "今天":
        return today, today
    if text == "昨天":
        return today - timedelta(days=1), today - timedelta(days=1)
    if text == "本周":
        return monday, sunday
    if text == "上周":
        return monday - timedelta(days=7), sunday - timedelta(days=7)
    if text == "本月":
        return _month_boundaries(today.year, today.month)
    if text == "上月":
        return _prev_month(today)
    if text == "本季度":
        return _quarter_bounds(today)
    if text == "今年":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    return None, None


# ---------------------------------------------------------------------------
# Fixed-date periods
# ---------------------------------------------------------------------------


def _try_fixed(text: str, today: date) -> tuple[date | None, date | None]:
    period = FIXED_DATE_PERIODS.get(text)
    if not period:
        return None, None
    sm, sd = int(period[0][:2]), int(period[0][3:])
    em, ed = int(period[1][:2]), int(period[1][3:])
    start = date(today.year, sm, sd)
    end = date(today.year, em, ed)
    if start > today:  # period already passed this year — use last year
        start = date(today.year - 1, sm, sd)
        end = date(today.year - 1, em, ed)
    return start, end


# ---------------------------------------------------------------------------
# Absolute time
# ---------------------------------------------------------------------------

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_DATETIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})")
_CN_DATE = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")
_CN_YM = re.compile(r"^(\d{4})年(\d{1,2})月$")


def _try_absolute(text: str) -> date | tuple[date, date] | None:
    m = _ISO_DATE.match(text) or _ISO_DATETIME.match(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = _CN_DATE.match(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = _CN_YM.match(text)
    if m:
        y, mo = int(m[1]), int(m[2])
        _, last = calendar.monthrange(y, mo)
        return date(y, mo, 1), date(y, mo, last)
    return None
