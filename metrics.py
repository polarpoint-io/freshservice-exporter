"""Aggregate Freshservice records into a metrics snapshot for Prometheus export."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from constants import (
    CHANGE_APPROVAL,
    CHANGE_RISK,
    CHANGE_STATUS,
    CHANGE_TYPE,
    OPEN_CHANGE_STATUSES,
    OPEN_PROBLEM_STATUSES,
    OPEN_RELEASE_STATUSES,
    OPEN_TICKET_STATUSES,
    PROBLEM_STATUS,
    RELEASE_STATUS,
    RELEASE_TYPE,
    TICKET_IMPACT,
    TICKET_PRIORITY,
    TICKET_SOURCE,
    TICKET_STATUS,
    UNKNOWN,
    age_bucket,
    label,
    optional_id,
)
from dora import compute_dora_metrics, parse_ts


def _inc(table: dict, key, amount: int = 1) -> None:
    table[key] = table.get(key, 0) + amount


def _add_sum_count(
    sums: dict,
    counts: dict,
    key,
    value: float,
) -> None:
    sums[key] = sums.get(key, 0.0) + value
    counts[key] = counts.get(key, 0) + 1


@dataclass
class MetricsSnapshot:
    # Tickets
    tickets_total: int = 0
    tickets_by_status: dict[str, int] = field(default_factory=dict)
    tickets_by_priority: dict[str, int] = field(default_factory=dict)
    tickets_by_type: dict[str, int] = field(default_factory=dict)
    tickets_by_group: dict[str, int] = field(default_factory=dict)
    tickets_by_category: dict[str, int] = field(default_factory=dict)
    tickets_by_department: dict[str, int] = field(default_factory=dict)
    tickets_by_workspace: dict[str, int] = field(default_factory=dict)
    tickets_by_source: dict[str, int] = field(default_factory=dict)
    tickets_by_impact: dict[str, int] = field(default_factory=dict)
    tickets_by_status_priority: dict[tuple[str, str], int] = field(default_factory=dict)
    tickets_by_type_status: dict[tuple[str, str], int] = field(default_factory=dict)
    tickets_open_by_priority: dict[str, int] = field(default_factory=dict)
    tickets_open_age_bucket: dict[str, int] = field(default_factory=dict)
    tickets_unassigned_open: int = 0
    tickets_escalated_open: int = 0
    tickets_overdue_open: int = 0
    tickets_fr_overdue_open: int = 0
    tickets_spam: int = 0
    tickets_resolved_in_window: dict[str, int] = field(default_factory=dict)
    ticket_resolution_seconds_sum: dict[tuple[str, str], float] = field(default_factory=dict)
    ticket_resolution_seconds_count: dict[tuple[str, str], int] = field(default_factory=dict)
    ticket_first_response_seconds_sum: dict[tuple[str, str], float] = field(default_factory=dict)
    ticket_first_response_seconds_count: dict[tuple[str, str], int] = field(default_factory=dict)

    # Changes
    changes_total: int = 0
    changes_by_status: dict[str, int] = field(default_factory=dict)
    changes_by_priority: dict[str, int] = field(default_factory=dict)
    changes_by_risk: dict[str, int] = field(default_factory=dict)
    changes_by_type: dict[str, int] = field(default_factory=dict)
    changes_by_group: dict[str, int] = field(default_factory=dict)
    changes_by_department: dict[str, int] = field(default_factory=dict)
    changes_by_approval_status: dict[str, int] = field(default_factory=dict)
    changes_by_status_type: dict[tuple[str, str], int] = field(default_factory=dict)
    changes_by_status_risk: dict[tuple[str, str], int] = field(default_factory=dict)
    changes_open_by_type: dict[str, int] = field(default_factory=dict)
    changes_open_age_bucket: dict[str, int] = field(default_factory=dict)
    changes_emergency_open: int = 0
    changes_overdue_open: int = 0
    changes_closed_in_window: dict[str, int] = field(default_factory=dict)
    change_cycle_seconds_sum: dict[str, float] = field(default_factory=dict)
    change_cycle_seconds_count: dict[str, int] = field(default_factory=dict)
    change_approval_to_close_seconds_sum: dict[str, float] = field(default_factory=dict)
    change_approval_to_close_seconds_count: dict[str, int] = field(default_factory=dict)

    # Releases
    releases_total: int = 0
    releases_by_status: dict[str, int] = field(default_factory=dict)
    releases_by_type: dict[str, int] = field(default_factory=dict)
    releases_by_priority: dict[str, int] = field(default_factory=dict)
    releases_by_type_status: dict[tuple[str, str], int] = field(default_factory=dict)
    releases_open_by_type: dict[str, int] = field(default_factory=dict)
    releases_open_age_bucket: dict[str, int] = field(default_factory=dict)
    releases_overdue_open: int = 0
    releases_completed_in_window: dict[str, int] = field(default_factory=dict)
    releases_failed_in_window: dict[str, int] = field(default_factory=dict)
    release_work_duration_seconds_sum: dict[str, float] = field(default_factory=dict)
    release_work_duration_seconds_count: dict[str, int] = field(default_factory=dict)

    # Problems
    problems_total: int = 0
    problems_by_status: dict[str, int] = field(default_factory=dict)
    problems_by_priority: dict[str, int] = field(default_factory=dict)
    problems_by_impact: dict[str, int] = field(default_factory=dict)
    problems_by_status_impact: dict[tuple[str, str], int] = field(default_factory=dict)
    problems_known_error: int = 0
    problems_open: int = 0
    problems_open_age_bucket: dict[str, int] = field(default_factory=dict)
    problems_overdue_open: int = 0

    # Assets
    assets_total: int = 0
    assets_by_type: dict[str, int] = field(default_factory=dict)

    # DORA (embedded)
    dora: Any = None


def aggregate_metrics(
    *,
    tickets: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    problems: list[dict[str, Any]],
    releases: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    config: dict[str, Any],
) -> MetricsSnapshot:
    now = datetime.now(tz=UTC)
    lookback_days = int(config.get("lookback_days", 30))
    window_start = now - timedelta(days=lookback_days)
    closed_change_status = int(config.get("closed_change_status", 6))

    snap = MetricsSnapshot()

    for ticket in tickets:
        snap.tickets_total += 1
        status = label(TICKET_STATUS, ticket.get("status"))
        priority = label(TICKET_PRIORITY, ticket.get("priority"))
        ticket_type = str(ticket.get("type") or UNKNOWN).lower()
        group = optional_id(ticket.get("group_id"))
        department = optional_id(ticket.get("department_id"))
        workspace = optional_id(ticket.get("workspace_id"))
        source = label(TICKET_SOURCE, ticket.get("source"))
        impact = label(TICKET_IMPACT, ticket.get("impact"))
        status_code = int(ticket.get("status", 0))

        _inc(snap.tickets_by_status, status)
        _inc(snap.tickets_by_priority, priority)
        _inc(snap.tickets_by_type, ticket_type)
        _inc(snap.tickets_by_group, group)
        _inc(snap.tickets_by_department, department)
        _inc(snap.tickets_by_workspace, workspace)
        _inc(snap.tickets_by_source, source)
        _inc(snap.tickets_by_impact, impact)
        _inc(snap.tickets_by_status_priority, (status, priority))
        _inc(snap.tickets_by_type_status, (ticket_type, status))
        _inc(snap.tickets_by_category, str(ticket.get("category") or UNKNOWN).lower())

        if ticket.get("spam"):
            snap.tickets_spam += 1

        created_at = parse_ts(ticket.get("created_at"))
        due_by = parse_ts(ticket.get("due_by"))
        fr_due_by = parse_ts(ticket.get("fr_due_by"))
        stats = ticket.get("stats") if isinstance(ticket.get("stats"), dict) else {}
        resolved_at = parse_ts(stats.get("resolved_at"))
        closed_at = parse_ts(stats.get("closed_at"))
        first_responded_at = parse_ts(stats.get("first_responded_at"))
        restored_at = resolved_at or closed_at

        if status_code in OPEN_TICKET_STATUSES:
            _inc(snap.tickets_open_by_priority, priority)
            if not ticket.get("responder_id"):
                snap.tickets_unassigned_open += 1
            if ticket.get("is_escalated") or ticket.get("fr_escalated"):
                snap.tickets_escalated_open += 1
            if due_by and due_by < now:
                snap.tickets_overdue_open += 1
            if fr_due_by and fr_due_by < now:
                snap.tickets_fr_overdue_open += 1
            if created_at:
                _inc(snap.tickets_open_age_bucket, age_bucket((now - created_at).total_seconds()))

        if restored_at and restored_at >= window_start:
            _inc(snap.tickets_resolved_in_window, ticket_type)
            if created_at and restored_at >= created_at:
                duration = (restored_at - created_at).total_seconds()
                _add_sum_count(
                    snap.ticket_resolution_seconds_sum,
                    snap.ticket_resolution_seconds_count,
                    (ticket_type, priority),
                    duration,
                )
            if created_at and first_responded_at and first_responded_at >= created_at:
                fr_duration = (first_responded_at - created_at).total_seconds()
                _add_sum_count(
                    snap.ticket_first_response_seconds_sum,
                    snap.ticket_first_response_seconds_count,
                    (ticket_type, priority),
                    fr_duration,
                )

    for change in changes:
        snap.changes_total += 1
        status = label(CHANGE_STATUS, change.get("status"))
        priority = label(TICKET_PRIORITY, change.get("priority"))
        risk = label(CHANGE_RISK, change.get("risk"))
        change_type = label(CHANGE_TYPE, change.get("change_type"))
        group = optional_id(change.get("group_id"))
        department = optional_id(change.get("department_id"))
        approval = label(CHANGE_APPROVAL, change.get("approval_status"))
        status_code = int(change.get("status", 0))
        type_code = int(change.get("change_type", 0))

        _inc(snap.changes_by_status, status)
        _inc(snap.changes_by_priority, priority)
        _inc(snap.changes_by_risk, risk)
        _inc(snap.changes_by_type, change_type)
        _inc(snap.changes_by_group, group)
        _inc(snap.changes_by_department, department)
        _inc(snap.changes_by_approval_status, approval)
        _inc(snap.changes_by_status_type, (status, change_type))
        _inc(snap.changes_by_status_risk, (status, risk))

        created_at = parse_ts(change.get("created_at"))
        planned_end = parse_ts(change.get("planned_end_date"))
        stats = change.get("stats") if isinstance(change.get("stats"), dict) else {}
        closed_at = parse_ts(stats.get("closed_at")) or parse_ts(change.get("updated_at"))
        approval_at = parse_ts(stats.get("approval_at"))

        if status_code in OPEN_CHANGE_STATUSES:
            _inc(snap.changes_open_by_type, change_type)
            if type_code == 4:
                snap.changes_emergency_open += 1
            if planned_end and planned_end < now:
                snap.changes_overdue_open += 1
            if created_at:
                _inc(snap.changes_open_age_bucket, age_bucket((now - created_at).total_seconds()))

        if status_code == closed_change_status and closed_at and closed_at >= window_start:
            _inc(snap.changes_closed_in_window, change_type)
            if created_at and closed_at >= created_at:
                cycle = (closed_at - created_at).total_seconds()
                _add_sum_count(
                    snap.change_cycle_seconds_sum,
                    snap.change_cycle_seconds_count,
                    change_type,
                    cycle,
                )
            if approval_at and closed_at >= approval_at:
                approval_cycle = (closed_at - approval_at).total_seconds()
                _add_sum_count(
                    snap.change_approval_to_close_seconds_sum,
                    snap.change_approval_to_close_seconds_count,
                    change_type,
                    approval_cycle,
                )

    for release in releases:
        snap.releases_total += 1
        status = label(RELEASE_STATUS, release.get("status"))
        release_type = label(RELEASE_TYPE, release.get("release_type"))
        priority = label(TICKET_PRIORITY, release.get("priority"))
        status_code = int(release.get("status", 0))

        _inc(snap.releases_by_status, status)
        _inc(snap.releases_by_type, release_type)
        _inc(snap.releases_by_priority, priority)
        _inc(snap.releases_by_type_status, (release_type, status))

        created_at = parse_ts(release.get("created_at"))
        planned_end = parse_ts(release.get("planned_end_date"))
        work_start = parse_ts(release.get("work_start_date"))
        work_end = parse_ts(release.get("work_end_date"))
        completed_at = work_end or parse_ts(release.get("updated_at")) or created_at

        if status_code in OPEN_RELEASE_STATUSES:
            _inc(snap.releases_open_by_type, release_type)
            if planned_end and planned_end < now:
                snap.releases_overdue_open += 1
            if created_at:
                _inc(snap.releases_open_age_bucket, age_bucket((now - created_at).total_seconds()))

        if completed_at and completed_at >= window_start:
            if status_code == 5:
                _inc(snap.releases_completed_in_window, release_type)
            elif status_code == 4:
                _inc(snap.releases_failed_in_window, release_type)

        if work_start and work_end and work_end >= work_start:
            duration = (work_end - work_start).total_seconds()
            _add_sum_count(
                snap.release_work_duration_seconds_sum,
                snap.release_work_duration_seconds_count,
                release_type,
                duration,
            )

    for problem in problems:
        snap.problems_total += 1
        status = label(PROBLEM_STATUS, problem.get("status"))
        priority = label(TICKET_PRIORITY, problem.get("priority"))
        impact = label(TICKET_IMPACT, problem.get("impact"))
        status_code = int(problem.get("status", 0))

        _inc(snap.problems_by_status, status)
        _inc(snap.problems_by_priority, priority)
        _inc(snap.problems_by_impact, impact)
        _inc(snap.problems_by_status_impact, (status, impact))

        if problem.get("known_error"):
            snap.problems_known_error += 1

        created_at = parse_ts(problem.get("created_at"))
        due_by = parse_ts(problem.get("due_by"))

        if status_code in OPEN_PROBLEM_STATUSES:
            snap.problems_open += 1
            if due_by and due_by < now:
                snap.problems_overdue_open += 1
            if created_at:
                _inc(snap.problems_open_age_bucket, age_bucket((now - created_at).total_seconds()))

    for asset in assets:
        snap.assets_total += 1
        asset_type = str(asset.get("asset_type_id") or asset.get("type") or UNKNOWN).lower()
        _inc(snap.assets_by_type, asset_type)

    if config.get("enable_dora"):
        snap.dora = compute_dora_metrics(
            tickets=tickets,
            changes=changes,
            releases=releases,
            config=config,
            ticket_priority_labels=TICKET_PRIORITY,
            change_type_labels=CHANGE_TYPE,
        )

    return snap
