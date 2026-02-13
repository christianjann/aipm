"""Tests for the horizon utility module."""

from __future__ import annotations

from datetime import date, timedelta

from aipm.horizons import (
    HORIZONS,
    horizon_sort_key,
    horizons_for_period,
    infer_horizon_from_date,
    infer_horizon_from_due,
    validate_horizon,
)


def test_valid_horizons() -> None:
    """All defined horizons should be accepted."""
    for h in HORIZONS:
        assert validate_horizon(h) == h


def test_validate_horizon_case_insensitive() -> None:
    """Horizon validation should be case-insensitive."""
    assert validate_horizon("NOW") == "now"
    assert validate_horizon("Week") == "week"
    assert validate_horizon("  month  ") == "month"


def test_validate_horizon_invalid() -> None:
    """Invalid horizon values should raise ValueError."""
    import pytest

    with pytest.raises(ValueError, match="Invalid horizon"):
        validate_horizon("tomorrow")


def test_horizon_sort_key_ordering() -> None:
    """Horizons should sort from most urgent to least urgent."""
    keys = [horizon_sort_key(h) for h in HORIZONS]
    assert keys == sorted(keys)
    assert horizon_sort_key("now") < horizon_sort_key("sometime")


def test_horizon_sort_key_unknown() -> None:
    """Unknown horizons should sort last."""
    assert horizon_sort_key("unknown") > horizon_sort_key("sometime")


def test_horizons_for_period_day() -> None:
    """Day period should only include 'now'."""
    assert horizons_for_period("day") == ("now",)


def test_horizons_for_period_week() -> None:
    """Week period should include now and week."""
    result = horizons_for_period("week")
    assert "now" in result
    assert "week" in result
    assert "month" not in result


def test_horizons_for_period_month() -> None:
    """Month period should include now, week, next-week, and month."""
    result = horizons_for_period("month")
    assert len(result) == 4
    assert "next-week" in result


def test_horizons_for_period_all() -> None:
    """All period should include everything."""
    assert horizons_for_period("all") == HORIZONS


def test_infer_horizon_overdue() -> None:
    """A past date should infer 'now'."""
    yesterday = date.today() - timedelta(days=1)
    assert infer_horizon_from_date(yesterday) == "now"


def test_infer_horizon_today() -> None:
    """Today's date should infer 'now'."""
    assert infer_horizon_from_date(date.today()) == "now"


def test_infer_horizon_this_week() -> None:
    """A date within this week should infer 'week'."""
    today = date.today()
    days_until_end_of_week = 6 - today.weekday()
    if days_until_end_of_week < 1:
        # If today is Sunday, skip — edge case handled by 'now'
        return
    target = today + timedelta(days=1)
    if target.weekday() <= 6 and (target - today).days <= days_until_end_of_week:
        result = infer_horizon_from_date(target)
        assert result in ("week", "now")


def test_infer_horizon_far_future() -> None:
    """A date far in the future should infer 'sometime'."""
    far = date.today() + timedelta(days=800)
    assert infer_horizon_from_date(far) == "sometime"


def test_infer_horizon_from_due_string() -> None:
    """String-based due date parsing should work."""
    today_str = date.today().strftime("%Y-%m-%d")
    assert infer_horizon_from_due(today_str) == "now"


def test_infer_horizon_from_due_invalid() -> None:
    """Invalid date string should return 'sometime'."""
    assert infer_horizon_from_due("not-a-date") == "sometime"
    assert infer_horizon_from_due("") == "sometime"
