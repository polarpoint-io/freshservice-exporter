from datetime import UTC, datetime, timedelta

from metrics import aggregate_metrics


def _ts(days_ago: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_aggregate_ticket_and_release_metrics():
    tickets = [
        {
            "type": "Incident",
            "status": 2,
            "priority": 4,
            "source": 2,
            "impact": 3,
            "group_id": None,
            "department_id": 10,
            "workspace_id": 1,
            "created_at": _ts(5),
            "due_by": _ts(0.5),
            "fr_due_by": _ts(0.5),
            "is_escalated": True,
            "stats": {},
        },
        {
            "type": "Incident",
            "status": 4,
            "priority": 3,
            "source": 1,
            "impact": 2,
            "group_id": 5,
            "department_id": 10,
            "workspace_id": 1,
            "created_at": _ts(10),
            "stats": {"resolved_at": _ts(9), "first_responded_at": _ts(9.5)},
        },
    ]
    releases = [
        {
            "status": 5,
            "release_type": 2,
            "priority": 2,
            "agent_id": 3,
            "group_id": 7,
            "department_id": 10,
            "workspace_id": 1,
            "category": "Software",
            "associated_changes": [11, 12],
            "work_start_date": _ts(3),
            "work_end_date": _ts(2),
            "planned_end_date": _ts(2.5),
            "created_at": _ts(4),
        },
        {
            "status": 3,
            "release_type": 4,
            "priority": 1,
            "group_id": None,
            "planned_end_date": _ts(0.5),
            "created_at": _ts(1),
            "planning_fields": {
                "build_plan": {"description": "Build on staging"},
                "test_plan": {"description": ""},
            },
        },
    ]

    snap = aggregate_metrics(
        tickets=tickets,
        changes=[],
        problems=[],
        releases=releases,
        assets=[],
        config={"lookback_days": 30, "enable_dora": True, "closed_change_status": 6},
    )

    assert snap.tickets_total == 2
    assert snap.tickets_unassigned_open == 1
    assert snap.tickets_escalated_open == 1
    assert snap.tickets_overdue_open == 1
    assert snap.tickets_by_status_priority[("open", "urgent")] == 1
    assert snap.ticket_resolution_seconds_count[("incident", "high")] == 1
    assert snap.releases_completed_in_window["standard"] == 1
    assert snap.releases_overdue_open == 1
    assert snap.releases_by_group["7"] == 1
    assert snap.releases_by_department["10"] == 1
    assert snap.releases_by_category["software"] == 1
    assert snap.releases_by_workspace["1"] == 1
    assert snap.releases_unassigned_open == 1
    assert snap.releases_emergency_open == 1
    assert snap.releases_linked_to_changes == 1
    assert snap.release_associated_changes == 2
    assert snap.releases_late_in_window["standard"] == 1
    assert snap.release_cycle_seconds_count["standard"] == 1
    assert snap.release_schedule_slip_seconds_count["standard"] == 1
    assert snap.release_schedule_slip_seconds_sum["standard"] > 0
    assert snap.releases_missing_build_plan_open == 0
    assert snap.releases_missing_test_plan_open == 1
    assert snap.dora is not None
    assert snap.dora.mttr_incident_count == 1
