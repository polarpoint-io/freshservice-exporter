"""Label maps and shared helpers for Freshservice metrics."""

from __future__ import annotations

UNKNOWN = "unknown"

TICKET_STATUS = {2: "open", 3: "pending", 4: "resolved", 5: "closed"}
TICKET_PRIORITY = {1: "low", 2: "medium", 3: "high", 4: "urgent"}
TICKET_IMPACT = {1: "low", 2: "medium", 3: "high"}
TICKET_SOURCE = {
    1: "email",
    2: "portal",
    3: "phone",
    4: "chat",
    5: "feedback_widget",
    6: "yumiot",
    7: "aws_cloudwatch",
    8: "slack",
    9: "kallesi",
    10: "canned_response",
}

CHANGE_STATUS = {
    1: "open",
    2: "planning",
    3: "approval",
    4: "pending_release",
    5: "pending_review",
    6: "closed",
}
CHANGE_RISK = {1: "low", 2: "medium", 3: "high", 4: "very_high"}
CHANGE_TYPE = {1: "minor", 2: "standard", 3: "major", 4: "emergency"}
CHANGE_APPROVAL = {1: "not_requested", 2: "requested", 3: "approved", 4: "rejected"}

PROBLEM_STATUS = {1: "open", 2: "change_requested", 3: "closed"}

RELEASE_STATUS = {1: "open", 2: "on_hold", 3: "in_progress", 4: "incomplete", 5: "completed"}
RELEASE_TYPE = {1: "minor", 2: "standard", 3: "major", 4: "emergency"}

AGE_BUCKETS = (
    ("1d", 86400),
    ("3d", 3 * 86400),
    ("7d", 7 * 86400),
    ("30d", 30 * 86400),
    ("90d", 90 * 86400),
)

OPEN_TICKET_STATUSES = {2, 3}
OPEN_CHANGE_STATUSES = {1, 2, 3, 4, 5}
OPEN_RELEASE_STATUSES = {1, 2, 3}
OPEN_PROBLEM_STATUSES = {1, 2}


def label(mapping: dict[int, str], value: object, *, default: str = UNKNOWN) -> str:
    try:
        return mapping.get(int(value), default if value in (None, "") else str(value))
    except (TypeError, ValueError):
        return default


def optional_id(value: object) -> str:
    if value in (None, "", 0):
        return "unassigned"
    return str(value)


def age_bucket(seconds: float) -> str:
    for name, upper in AGE_BUCKETS:
        if seconds <= upper:
            return name
    return "older"
