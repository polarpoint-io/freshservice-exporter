"""Integration tests for the Prometheus collector with a mocked API client."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from exporter import FreshserviceCollector


def _ts(days_ago: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeClient:
    def __init__(self) -> None:
        self.last_ticket_params: dict | None = None
        self.last_change_params: dict | None = None

    def list_tickets(self, **params):
        self.last_ticket_params = params
        return iter(self._tickets())

    def list_changes(self, **params):
        self.last_change_params = params
        return iter(self._changes())

    def list_problems(self, **params):
        return iter(self._problems())

    def list_releases(self, **params):
        return iter(self._releases())

    def list_assets(self, **params):
        return iter(self._assets())

    def collect_list(self, list_fn, **params):
        return list(list_fn(**params))

    def _tickets(self):
        return [
            {
                "type": "Incident",
                "status": 4,
                "priority": 3,
                "source": 2,
                "impact": 2,
                "group_id": 1,
                "department_id": 2,
                "workspace_id": 1,
                "category": "Network",
                "created_at": _ts(5),
                "stats": {"resolved_at": _ts(4), "first_responded_at": _ts(4.5)},
            }
        ]

    def _changes(self):
        return [
            {
                "status": 6,
                "priority": 2,
                "risk": 1,
                "change_type": 2,
                "group_id": 1,
                "department_id": 2,
                "approval_status": 3,
                "created_at": _ts(8),
                "stats": {"closed_at": _ts(6), "approval_at": _ts(7)},
            }
        ]

    def _problems(self):
        return [{"status": 1, "priority": 2, "impact": 2, "known_error": True, "created_at": _ts(2)}]

    def _releases(self):
        return [
            {
                "status": 5,
                "release_type": 2,
                "priority": 2,
                "work_start_date": _ts(3),
                "work_end_date": _ts(2),
                "created_at": _ts(4),
            }
        ]

    def _assets(self):
        return [{"asset_type_id": 42}]


def _collect_metric_names(collector: FreshserviceCollector) -> set[str]:
    names: set[str] = set()
    for family in collector.collect():
        names.add(family.name)
    return names


def test_collector_emits_core_metric_families():
    config = {
        "workspace_id": None,
        "updated_since": _ts(30),
        "enable_tickets": True,
        "enable_changes": True,
        "enable_problems": True,
        "enable_assets": True,
        "enable_dora": True,
        "enable_releases": True,
        "include_stats": True,
        "lookback_days": 30,
        "mttr_ticket_types": "Incident",
        "closed_change_status": 6,
    }
    collector = FreshserviceCollector(FakeClient(), config)
    names = _collect_metric_names(collector)

    expected = {
        "freshservice_tickets_total",
        "freshservice_tickets_by_status_total",
        "freshservice_ticket_resolution_duration_seconds_sum",
        "freshservice_changes_total",
        "freshservice_change_cycle_duration_seconds_sum",
        "freshservice_releases_total",
        "freshservice_releases_completed_in_window_total",
        "freshservice_problems_known_error_total",
        "freshservice_assets_total",
        "freshservice_dora_mttr_seconds",
        "freshservice_exporter_last_scrape_successful",
    }
    missing = expected - names
    assert not missing, f"Missing metrics: {missing}"


def test_collector_records_api_failure():
    class BrokenClient:
        def list_tickets(self, **params):
            raise RuntimeError("boom")

        def collect_list(self, list_fn, **params):
            return list(list_fn(**params))

    config = {
        "workspace_id": None,
        "updated_since": _ts(30),
        "enable_tickets": True,
        "enable_changes": False,
        "enable_problems": False,
        "enable_assets": False,
        "enable_dora": False,
        "enable_releases": False,
        "include_stats": True,
        "lookback_days": 30,
        "mttr_ticket_types": "Incident",
        "closed_change_status": 6,
    }
    collector = FreshserviceCollector(BrokenClient(), config)
    list(collector.collect())
    assert collector._last_scrape_success == 0
    assert collector._api_errors == 1


def test_include_stats_applies_to_tickets_only():
    client = FakeClient()
    config = {
        "workspace_id": None,
        "updated_since": _ts(30),
        "enable_tickets": True,
        "enable_changes": True,
        "enable_problems": False,
        "enable_assets": False,
        "enable_dora": True,
        "enable_releases": False,
        "include_stats": True,
        "lookback_days": 30,
        "mttr_ticket_types": "Incident",
        "closed_change_status": 6,
    }
    collector = FreshserviceCollector(client, config)
    list(collector.collect())

    assert client.last_ticket_params is not None
    assert client.last_change_params is not None
    assert client.last_ticket_params.get("include") == "stats"
    assert "include" not in client.last_change_params
    assert collector._last_scrape_success == 1
