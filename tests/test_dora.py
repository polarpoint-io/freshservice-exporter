from datetime import UTC, datetime, timedelta

from dora import compute_dora_metrics


def _ts(days_ago: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_compute_dora_mttr_and_deployments():
    tickets = [
        {
            "type": "Incident",
            "status": 4,
            "priority": 3,
            "created_at": _ts(10),
            "stats": {"resolved_at": _ts(9), "first_responded_at": _ts(9.5)},
        },
        {
            "type": "Incident",
            "status": 2,
            "priority": 4,
            "created_at": _ts(1),
            "stats": {},
        },
        {
            "type": "Service Request",
            "status": 4,
            "priority": 1,
            "created_at": _ts(5),
            "stats": {"resolved_at": _ts(4)},
        },
    ]
    changes = [
        {
            "status": 6,
            "change_type": 2,
            "created_at": _ts(15),
            "stats": {"closed_at": _ts(12)},
        }
    ]
    releases = [
        {"status": 5, "work_end_date": _ts(2)},
        {"status": 4, "work_end_date": _ts(3)},
        {"status": 3, "work_end_date": _ts(1)},
    ]

    snapshot = compute_dora_metrics(
        tickets=tickets,
        changes=changes,
        releases=releases,
        config={"lookback_days": 30, "mttr_ticket_types": "Incident", "closed_change_status": 6},
        ticket_priority_labels={1: "low", 2: "medium", 3: "high", 4: "urgent"},
        change_type_labels={2: "standard"},
    )

    assert snapshot.mttr_incident_count == 1
    assert snapshot.mttr_seconds == 24 * 3600
    assert snapshot.first_response_seconds == 12 * 3600
    assert snapshot.lead_time_change_count == 1
    assert snapshot.deployments_total["success"] == 1
    assert snapshot.deployments_total["failed"] == 1
    assert snapshot.change_failure_rate == 0.5
    assert snapshot.open_incidents_by_priority["urgent"] == 1
