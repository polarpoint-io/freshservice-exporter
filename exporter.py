"""
Freshservice Prometheus Exporter

Exports Freshservice ITSM and DORA metrics for Grafana Cloud.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from prometheus_client import CollectorRegistry, start_http_server
from prometheus_client.core import GaugeMetricFamily

from client import FreshserviceClient, FreshserviceError
from emit import gauge, labeled_gauge, sum_count_pair
from metrics import MetricsSnapshot, aggregate_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("freshservice_exporter")


def _truthy(value: str | None, *, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _workspace_params(workspace_id: str | None) -> dict[str, Any]:
    if workspace_id is None or workspace_id == "":
        return {}
    return {"workspace_id": workspace_id}


class FreshserviceCollector:
    def __init__(self, client: FreshserviceClient, config: dict[str, Any]) -> None:
        self.client = client
        self.config = config
        self._snapshot: MetricsSnapshot | None = None
        self._last_scrape_timestamp = 0.0
        self._last_scrape_duration = 0.0
        self._last_scrape_success = 0
        self._api_errors = 0

    def _fetch_all(self) -> MetricsSnapshot:
        params = _workspace_params(self.config.get("workspace_id"))
        if self.config.get("updated_since"):
            params["updated_since"] = self.config["updated_since"]
        if self.config.get("include_stats"):
            params["include"] = "stats"

        tickets: list[dict[str, Any]] = []
        changes: list[dict[str, Any]] = []
        problems: list[dict[str, Any]] = []
        releases: list[dict[str, Any]] = []
        assets: list[dict[str, Any]] = []

        if self.config["enable_tickets"] or self.config["enable_dora"]:
            log.info("Fetching tickets …")
            tickets = self.client.collect_list(self.client.list_tickets, **params)

        if self.config["enable_changes"] or self.config["enable_dora"]:
            log.info("Fetching changes …")
            changes = self.client.collect_list(self.client.list_changes, **params)

        if self.config["enable_problems"]:
            log.info("Fetching problems …")
            problem_params = _workspace_params(self.config.get("workspace_id"))
            problems = self.client.collect_list(self.client.list_problems, **problem_params)

        if self.config["enable_releases"] or self.config["enable_dora"]:
            log.info("Fetching releases …")
            release_params = _workspace_params(self.config.get("workspace_id"))
            releases = self.client.collect_list(self.client.list_releases, **release_params)

        if self.config["enable_assets"]:
            log.info("Fetching assets …")
            asset_params = _workspace_params(self.config.get("workspace_id"))
            assets = self.client.collect_list(self.client.list_assets, **asset_params)

        return aggregate_metrics(
            tickets=tickets,
            changes=changes,
            problems=problems,
            releases=releases,
            assets=assets,
            config=self.config,
        )

    def collect(self) -> Iterable[GaugeMetricFamily]:
        started = time.monotonic()
        scrape_ok = 1
        try:
            self._snapshot = self._fetch_all()
        except FreshserviceError as exc:
            scrape_ok = 0
            self._api_errors += 1
            log.warning("Collection error: %s", exc)
            self._snapshot = MetricsSnapshot()
        except Exception as exc:
            scrape_ok = 0
            self._api_errors += 1
            log.exception("Unexpected collection error: %s", exc)
            self._snapshot = MetricsSnapshot()

        self._last_scrape_duration = time.monotonic() - started
        self._last_scrape_timestamp = time.time()
        self._last_scrape_success = scrape_ok

        snap = self._snapshot
        if snap is None:
            return

        yield from self._emit_tickets(snap)
        yield from self._emit_changes(snap)
        yield from self._emit_releases(snap)
        yield from self._emit_problems(snap)
        yield from self._emit_assets(snap)
        yield from self._emit_dora(snap)
        yield from self._emit_diagnostics()

        log.info("Metric collection complete in %.1fs", self._last_scrape_duration)

    def _emit_tickets(self, s: MetricsSnapshot) -> Iterable[GaugeMetricFamily]:
        if not self.config["enable_tickets"]:
            return

        yield gauge("freshservice_tickets_total", "Tickets in the current API fetch scope", s.tickets_total)
        yield labeled_gauge(
            "freshservice_tickets_by_status_total", "Tickets by status", ["status"], s.tickets_by_status
        )
        yield labeled_gauge(
            "freshservice_tickets_by_priority_total",
            "Tickets by priority",
            ["priority"],
            s.tickets_by_priority,
        )
        yield labeled_gauge(
            "freshservice_tickets_by_type_total", "Tickets by type", ["type"], s.tickets_by_type
        )
        yield labeled_gauge(
            "freshservice_tickets_by_group_total", "Tickets by group", ["group_id"], s.tickets_by_group
        )
        yield labeled_gauge(
            "freshservice_tickets_by_category_total",
            "Tickets by category",
            ["category"],
            s.tickets_by_category,
        )
        yield labeled_gauge(
            "freshservice_tickets_by_department_total",
            "Tickets by department",
            ["department_id"],
            s.tickets_by_department,
        )
        yield labeled_gauge(
            "freshservice_tickets_by_workspace_total",
            "Tickets by workspace",
            ["workspace_id"],
            s.tickets_by_workspace,
        )
        yield labeled_gauge(
            "freshservice_tickets_by_source_total", "Tickets by source", ["source"], s.tickets_by_source
        )
        yield labeled_gauge(
            "freshservice_tickets_by_impact_total", "Tickets by impact", ["impact"], s.tickets_by_impact
        )
        yield labeled_gauge(
            "freshservice_tickets_by_status_priority_total",
            "Tickets by status and priority",
            ["status", "priority"],
            s.tickets_by_status_priority,
        )
        yield labeled_gauge(
            "freshservice_tickets_by_type_status_total",
            "Tickets by type and status",
            ["type", "status"],
            s.tickets_by_type_status,
        )
        yield labeled_gauge(
            "freshservice_tickets_open_by_priority_total",
            "Open or pending tickets by priority",
            ["priority"],
            s.tickets_open_by_priority,
        )
        yield labeled_gauge(
            "freshservice_tickets_open_age_bucket_total",
            "Open tickets by age bucket",
            ["bucket"],
            s.tickets_open_age_bucket,
        )
        yield gauge(
            "freshservice_tickets_unassigned_open_total",
            "Open tickets with no assigned agent",
            s.tickets_unassigned_open,
        )
        yield gauge(
            "freshservice_tickets_escalated_open_total",
            "Open tickets that are escalated",
            s.tickets_escalated_open,
        )
        yield gauge(
            "freshservice_tickets_overdue_open_total",
            "Open tickets past resolution due_by",
            s.tickets_overdue_open,
        )
        yield gauge(
            "freshservice_tickets_first_response_overdue_open_total",
            "Open tickets past first-response due_by",
            s.tickets_fr_overdue_open,
        )
        yield gauge("freshservice_tickets_spam_total", "Tickets flagged as spam", s.tickets_spam)
        yield labeled_gauge(
            "freshservice_tickets_resolved_in_window_total",
            "Tickets resolved in the lookback window by type",
            ["type"],
            s.tickets_resolved_in_window,
        )
        yield from sum_count_pair(
            "freshservice_ticket_resolution_duration_seconds",
            "Ticket resolution time (resolved_at - created_at)",
            ["type", "priority"],
            s.ticket_resolution_seconds_sum,
            s.ticket_resolution_seconds_count,
        )
        yield from sum_count_pair(
            "freshservice_ticket_first_response_duration_seconds",
            "Ticket first-response time (first_responded_at - created_at)",
            ["type", "priority"],
            s.ticket_first_response_seconds_sum,
            s.ticket_first_response_seconds_count,
        )

    def _emit_changes(self, s: MetricsSnapshot) -> Iterable[GaugeMetricFamily]:
        if not self.config["enable_changes"]:
            return

        yield gauge("freshservice_changes_total", "Changes in the current API fetch scope", s.changes_total)
        yield labeled_gauge(
            "freshservice_changes_by_status_total", "Changes by status", ["status"], s.changes_by_status
        )
        yield labeled_gauge(
            "freshservice_changes_by_priority_total",
            "Changes by priority",
            ["priority"],
            s.changes_by_priority,
        )
        yield labeled_gauge(
            "freshservice_changes_by_risk_total", "Changes by risk", ["risk"], s.changes_by_risk
        )
        yield labeled_gauge(
            "freshservice_changes_by_type_total", "Changes by type", ["change_type"], s.changes_by_type
        )
        yield labeled_gauge(
            "freshservice_changes_by_group_total", "Changes by group", ["group_id"], s.changes_by_group
        )
        yield labeled_gauge(
            "freshservice_changes_by_department_total",
            "Changes by department",
            ["department_id"],
            s.changes_by_department,
        )
        yield labeled_gauge(
            "freshservice_changes_by_approval_status_total",
            "Changes by approval status",
            ["approval_status"],
            s.changes_by_approval_status,
        )
        yield labeled_gauge(
            "freshservice_changes_by_status_type_total",
            "Changes by status and type",
            ["status", "change_type"],
            s.changes_by_status_type,
        )
        yield labeled_gauge(
            "freshservice_changes_by_status_risk_total",
            "Changes by status and risk",
            ["status", "risk"],
            s.changes_by_status_risk,
        )
        yield labeled_gauge(
            "freshservice_changes_open_by_type_total",
            "Open changes by type",
            ["change_type"],
            s.changes_open_by_type,
        )
        yield labeled_gauge(
            "freshservice_changes_open_age_bucket_total",
            "Open changes by age bucket",
            ["bucket"],
            s.changes_open_age_bucket,
        )
        yield gauge(
            "freshservice_changes_emergency_open_total",
            "Open emergency changes",
            s.changes_emergency_open,
        )
        yield gauge(
            "freshservice_changes_overdue_open_total",
            "Open changes past planned_end_date",
            s.changes_overdue_open,
        )
        yield labeled_gauge(
            "freshservice_changes_closed_in_window_total",
            "Changes closed in the lookback window",
            ["change_type"],
            s.changes_closed_in_window,
        )
        yield from sum_count_pair(
            "freshservice_change_cycle_duration_seconds",
            "Change cycle time (closed_at - created_at)",
            ["change_type"],
            s.change_cycle_seconds_sum,
            s.change_cycle_seconds_count,
        )
        yield from sum_count_pair(
            "freshservice_change_approval_to_close_duration_seconds",
            "Change time from approval to close",
            ["change_type"],
            s.change_approval_to_close_seconds_sum,
            s.change_approval_to_close_seconds_count,
        )

    def _emit_releases(self, s: MetricsSnapshot) -> Iterable[GaugeMetricFamily]:
        if not self.config["enable_releases"]:
            return

        yield gauge("freshservice_releases_total", "Releases in the current API fetch scope", s.releases_total)
        yield labeled_gauge(
            "freshservice_releases_by_status_total", "Releases by status", ["status"], s.releases_by_status
        )
        yield labeled_gauge(
            "freshservice_releases_by_type_total",
            "Releases by type",
            ["release_type"],
            s.releases_by_type,
        )
        yield labeled_gauge(
            "freshservice_releases_by_priority_total",
            "Releases by priority",
            ["priority"],
            s.releases_by_priority,
        )
        yield labeled_gauge(
            "freshservice_releases_by_type_status_total",
            "Releases by type and status",
            ["release_type", "status"],
            s.releases_by_type_status,
        )
        yield labeled_gauge(
            "freshservice_releases_open_by_type_total",
            "Open releases by type",
            ["release_type"],
            s.releases_open_by_type,
        )
        yield labeled_gauge(
            "freshservice_releases_open_age_bucket_total",
            "Open releases by age bucket",
            ["bucket"],
            s.releases_open_age_bucket,
        )
        yield gauge(
            "freshservice_releases_overdue_open_total",
            "Open releases past planned_end_date",
            s.releases_overdue_open,
        )
        yield labeled_gauge(
            "freshservice_releases_completed_in_window_total",
            "Completed releases in the lookback window",
            ["release_type"],
            s.releases_completed_in_window,
        )
        yield labeled_gauge(
            "freshservice_releases_failed_in_window_total",
            "Failed (incomplete) releases in the lookback window",
            ["release_type"],
            s.releases_failed_in_window,
        )
        yield from sum_count_pair(
            "freshservice_release_work_duration_seconds",
            "Release work duration (work_end_date - work_start_date)",
            ["release_type"],
            s.release_work_duration_seconds_sum,
            s.release_work_duration_seconds_count,
        )

    def _emit_problems(self, s: MetricsSnapshot) -> Iterable[GaugeMetricFamily]:
        if not self.config["enable_problems"]:
            return

        yield gauge("freshservice_problems_total", "Problems in scope", s.problems_total)
        yield labeled_gauge(
            "freshservice_problems_by_status_total", "Problems by status", ["status"], s.problems_by_status
        )
        yield labeled_gauge(
            "freshservice_problems_by_priority_total",
            "Problems by priority",
            ["priority"],
            s.problems_by_priority,
        )
        yield labeled_gauge(
            "freshservice_problems_by_impact_total", "Problems by impact", ["impact"], s.problems_by_impact
        )
        yield labeled_gauge(
            "freshservice_problems_by_status_impact_total",
            "Problems by status and impact",
            ["status", "impact"],
            s.problems_by_status_impact,
        )
        yield gauge("freshservice_problems_known_error_total", "Problems marked as known error", s.problems_known_error)
        yield gauge("freshservice_problems_open_total", "Open problems", s.problems_open)
        yield labeled_gauge(
            "freshservice_problems_open_age_bucket_total",
            "Open problems by age bucket",
            ["bucket"],
            s.problems_open_age_bucket,
        )
        yield gauge(
            "freshservice_problems_overdue_open_total",
            "Open problems past due_by",
            s.problems_overdue_open,
        )

    def _emit_assets(self, s: MetricsSnapshot) -> Iterable[GaugeMetricFamily]:
        if not self.config["enable_assets"]:
            return

        yield gauge("freshservice_assets_total", "Assets in scope", s.assets_total)
        yield labeled_gauge(
            "freshservice_assets_by_type_total", "Assets by type", ["asset_type"], s.assets_by_type
        )

    def _emit_dora(self, s: MetricsSnapshot) -> Iterable[GaugeMetricFamily]:
        if not self.config["enable_dora"] or s.dora is None:
            return

        d = s.dora
        yield gauge(
            "freshservice_dora_mttr_seconds",
            "Mean time to restore for incidents resolved in the lookback window",
            d.mttr_seconds,
        )
        yield gauge(
            "freshservice_dora_mttr_incident_count",
            "Incident count used in MTTR calculation",
            float(d.mttr_incident_count),
        )
        yield gauge(
            "freshservice_dora_first_response_seconds",
            "Mean first-response time for incidents in the lookback window",
            d.first_response_seconds,
        )
        yield gauge(
            "freshservice_dora_first_response_incident_count",
            "Incident count used in first-response calculation",
            float(d.first_response_count),
        )
        yield gauge(
            "freshservice_dora_lead_time_seconds",
            "Mean lead time for closed changes in the lookback window",
            d.lead_time_seconds,
        )
        yield gauge(
            "freshservice_dora_lead_time_change_count",
            "Closed change count used in lead-time calculation",
            float(d.lead_time_change_count),
        )
        yield gauge(
            "freshservice_dora_deployment_frequency_per_day",
            "Completed plus failed releases per day in the lookback window",
            d.deployment_frequency_per_day,
        )
        yield gauge(
            "freshservice_dora_change_failure_rate",
            "Failed releases / (successful + failed releases) in the lookback window",
            d.change_failure_rate,
        )
        yield gauge(
            "freshservice_dora_lookback_days",
            "Configured DORA lookback window in days",
            float(d.lookback_days),
        )
        yield labeled_gauge(
            "freshservice_dora_deployments_total",
            "Releases in the lookback window by outcome",
            ["outcome"],
            d.deployments_total,
        )
        yield labeled_gauge(
            "freshservice_dora_open_incidents_total",
            "Open incidents by priority",
            ["priority"],
            d.open_incidents_by_priority,
        )

    def _emit_diagnostics(self) -> Iterable[GaugeMetricFamily]:
        yield gauge(
            "freshservice_exporter_last_scrape_timestamp",
            "Unix timestamp of the last completed scrape",
            self._last_scrape_timestamp,
        )
        yield gauge(
            "freshservice_exporter_last_scrape_duration_seconds",
            "Duration of the last scrape in seconds",
            self._last_scrape_duration,
        )
        yield gauge(
            "freshservice_exporter_last_scrape_successful",
            "1 if the last scrape completed without API errors, else 0",
            float(self._last_scrape_success),
        )
        yield gauge(
            "freshservice_exporter_api_errors_total",
            "Cumulative API collection errors since process start",
            float(self._api_errors),
        )


def _load_config() -> dict[str, Any]:
    lookback_days = int(os.environ.get("FRESHSERVICE_DORA_LOOKBACK_DAYS", "30"))
    updated_since = os.environ.get("FRESHSERVICE_UPDATED_SINCE")
    if not updated_since:
        updated_since = (datetime.now(tz=UTC) - timedelta(days=lookback_days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    return {
        "workspace_id": os.environ.get("FRESHSERVICE_WORKSPACE_ID"),
        "updated_since": updated_since,
        "enable_tickets": _truthy(os.environ.get("FRESHSERVICE_ENABLE_TICKETS"), default=True),
        "enable_changes": _truthy(os.environ.get("FRESHSERVICE_ENABLE_CHANGES"), default=True),
        "enable_problems": _truthy(os.environ.get("FRESHSERVICE_ENABLE_PROBLEMS"), default=True),
        "enable_assets": _truthy(os.environ.get("FRESHSERVICE_ENABLE_ASSETS"), default=False),
        "enable_dora": _truthy(os.environ.get("FRESHSERVICE_ENABLE_DORA"), default=True),
        "enable_releases": _truthy(os.environ.get("FRESHSERVICE_ENABLE_RELEASES"), default=True),
        "include_stats": _truthy(os.environ.get("FRESHSERVICE_INCLUDE_STATS"), default=True),
        "lookback_days": lookback_days,
        "mttr_ticket_types": os.environ.get("FRESHSERVICE_MTTR_TICKET_TYPES", "Incident"),
        "closed_change_status": int(os.environ.get("FRESHSERVICE_CLOSED_CHANGE_STATUS", "6")),
    }


def main() -> None:
    port = int(os.environ.get("EXPORTER_PORT", "9192"))
    scrape_interval = int(os.environ.get("SCRAPE_INTERVAL", "300"))
    config = _load_config()

    client = FreshserviceClient.from_env()
    registry = CollectorRegistry()
    registry.register(FreshserviceCollector(client, config))

    start_http_server(port, registry=registry)
    log.info("Freshservice exporter listening on :%d", port)

    while True:
        time.sleep(scrape_interval)


if __name__ == "__main__":
    main()
