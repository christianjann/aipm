"""Time horizon utilities for AIPM planning."""

from __future__ import annotations

from datetime import date, datetime

# Valid horizon values in urgency order
HORIZONS = ("now", "week", "next-week", "month", "year", "sometime")

# Which horizons are relevant for each summary period
PERIOD_HORIZONS: dict[str, tuple[str, ...]] = {
    "day": ("now",),
    "week": ("now", "week"),
    "month": ("now", "week", "next-week", "month"),
    "year": ("now", "week", "next-week", "month", "year"),
    "all": HORIZONS,
}


def infer_horizon_from_due(due_str: str) -> str:
    """Infer the best-matching horizon from a due date string (YYYY-MM-DD).

    Returns the inferred horizon, or 'sometime' if the date cannot be parsed.
    """
    try:
        due = datetime.strptime(due_str, "%Y-%m-%d").date()
    except ValueError, TypeError:
        return "sometime"

    return infer_horizon_from_date(due)


def infer_horizon_from_date(due: date) -> str:
    """Infer the best-matching horizon from a date object."""
    today = date.today()
    delta = (due - today).days

    if delta <= 0:
        return "now"

    # This week: remaining days until end of week (Sunday)
    days_until_end_of_week = 6 - today.weekday()  # Monday=0, Sunday=6
    if delta <= days_until_end_of_week:
        return "week"

    # Next week: within 7 days after this week ends
    if delta <= days_until_end_of_week + 7:
        return "next-week"

    # This or next month: within ~60 days
    if delta <= 60:
        return "month"

    # This year
    end_of_year = date(today.year, 12, 31)
    if due <= end_of_year:
        return "year"

    return "sometime"


def validate_horizon(value: str) -> str:
    """Validate and normalize a horizon value. Raises ValueError if invalid."""
    normalized = value.strip().lower()
    if normalized not in HORIZONS:
        valid = ", ".join(HORIZONS)
        msg = f"Invalid horizon '{value}'. Must be one of: {valid}"
        raise ValueError(msg)
    return normalized


def horizon_sort_key(horizon: str) -> int:
    """Return a sort key for a horizon (lower = more urgent)."""
    try:
        return HORIZONS.index(horizon.lower())
    except ValueError:
        return len(HORIZONS)  # Unknown horizons sort last


def horizons_for_period(period: str) -> tuple[str, ...]:
    """Return which horizons are relevant for a given summary period."""
    return PERIOD_HORIZONS.get(period, HORIZONS)


# Human-readable labels for display
HORIZON_LABELS: dict[str, str] = {
    "now": "Now — urgent",
    "week": "This Week",
    "next-week": "Next Week",
    "month": "This / Next Month",
    "year": "This Year",
    "sometime": "Sometime",
}
