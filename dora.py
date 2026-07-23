"""DORA metric calculations from Freshservice ITSM data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

RELEASE_STATUS = {
    1: "open",
    2: "on_hold",
    3: "in_progress",
    4: "incomplete",
    5: "completed",
}

RELEASE_TYPE = {
    1: "minor",
    2: "standard",
    3: "major",
    4: "emergency",
}


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _in_window(ts: datetime | None, window_start: datetime) -> bool:
    return ts is not None and ts >= window_start


def _ticket_types(config: dict[str, Any]) -> set[str]:
    raw = config.get("mttr_ticket_types") or "Incident"
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


@dataclass
class DoraSnapshot:
    lookback_days: int = 30
    mttr_seconds: float = 0.0
    mttr_incident_count: int = 0
    first_response_seconds: float = 0.0
    first_response_count: int = 0
    lead_time_seconds: float = 0.0
    lead_time_change_count: int = 0
    deployment_frequency_per_day: float = 0.0
    change_failure_rate: float = 0.0
    deployments_total: dict[str, int] = field(default_factory=dict)
    releases_by_status: dict[str, int] = field(default_factory=dict)
    changes_closed_by_type: dict[str, int] = field(default_factory=dict)
    open_incidents_by_priority: dict[str, int] = field(default_factory=dict)


def compute_dora_metrics(
    *,
    tickets: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    releases: list[dict[str, Any]],
    config: dict[str, Any],
    ticket_priority_labels: dict[int, str],
    change_type_labels: dict[int, str],
) -> DoraSnapshot:
    lookback_days = int(config.get("lookback_days", 30))
    window_start = datetime.now(tz=UTC) - timedelta(days=lookback_days)
    mttr_types = _ticket_types(config)
    closed_change_status = int(config.get("closed_change_status", 6))

    recovery_seconds: list[float] = []
    response_seconds: list[float] = []
    lead_times: list[float] = []

    open_incidents: dict[str, int] = {}
    changes_closed: dict[str, int] = {}
    releases_by_status: dict[str, int] = {}
    deployments: dict[str, int] = {"success": 0, "failed": 0, "in_progress": 0}

    for ticket in tickets:
        ticket_type = str(ticket.get("type") or "").lower()
        priority = ticket_priority_labels.get(int(ticket.get("priority", 0)), "unknown")
        status = int(ticket.get("status", 0))
        created_at = parse_ts(ticket.get("created_at"))
        stats = ticket.get("stats") if isinstance(ticket.get("stats"), dict) else {}
        resolved_at = parse_ts(stats.get("resolved_at"))
        closed_at = parse_ts(stats.get("closed_at"))
        first_responded_at = parse_ts(stats.get("first_responded_at"))
        restored_at = resolved_at or closed_at

        if ticket_type in mttr_types and status in {2, 3}:
            open_incidents[priority] = open_incidents.get(priority, 0) + 1

        if ticket_type not in mttr_types or not _in_window(restored_at, window_start):
            continue

        if created_at and restored_at and restored_at >= created_at:
            recovery_seconds.append((restored_at - created_at).total_seconds())

        if created_at and first_responded_at and first_responded_at >= created_at:
            response_seconds.append((first_responded_at - created_at).total_seconds())

    for change in changes:
        status = int(change.get("status", 0))
        if status != closed_change_status:
            continue

        change_type = change_type_labels.get(int(change.get("change_type", 0)), "unknown")
        created_at = parse_ts(change.get("created_at"))
        stats = change.get("stats") if isinstance(change.get("stats"), dict) else {}
        closed_at = parse_ts(stats.get("closed_at")) or parse_ts(change.get("updated_at"))

        if not _in_window(closed_at, window_start):
            continue

        changes_closed[change_type] = changes_closed.get(change_type, 0) + 1
        if created_at and closed_at and closed_at >= created_at:
            lead_times.append((closed_at - created_at).total_seconds())

    for release in releases:
        status_code = int(release.get("status", 0))
        status = RELEASE_STATUS.get(status_code, str(status_code))
        releases_by_status[status] = releases_by_status.get(status, 0) + 1

        completed_at = (
            parse_ts(release.get("work_end_date"))
            or parse_ts(release.get("updated_at"))
            or parse_ts(release.get("created_at"))
        )
        if not _in_window(completed_at, window_start):
            continue

        if status_code == 5:
            deployments["success"] += 1
        elif status_code == 4:
            deployments["failed"] += 1
        elif status_code in {1, 2, 3}:
            deployments["in_progress"] += 1

    deployment_total = deployments["success"] + deployments["failed"]
    failure_rate = deployments["failed"] / deployment_total if deployment_total else 0.0
    deployment_frequency = deployment_total / lookback_days if lookback_days else 0.0

    return DoraSnapshot(
        lookback_days=lookback_days,
        mttr_seconds=sum(recovery_seconds) / len(recovery_seconds) if recovery_seconds else 0.0,
        mttr_incident_count=len(recovery_seconds),
        first_response_seconds=sum(response_seconds) / len(response_seconds)
        if response_seconds
        else 0.0,
        first_response_count=len(response_seconds),
        lead_time_seconds=sum(lead_times) / len(lead_times) if lead_times else 0.0,
        lead_time_change_count=len(lead_times),
        deployment_frequency_per_day=deployment_frequency,
        change_failure_rate=failure_rate,
        deployments_total=deployments,
        releases_by_status=releases_by_status,
        changes_closed_by_type=changes_closed,
        open_incidents_by_priority=open_incidents,
    )
