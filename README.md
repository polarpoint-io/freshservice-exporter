# freshservice-exporter

Prometheus exporter for [Freshservice](https://www.freshservice.com/) with a broad metric surface for **Grafana Cloud** — ITSM operations, SLA tracking, and DORA (MTTR, deployment frequency, change failure rate, lead time).

[![CI](https://github.com/polarpoint-io/freshservice-exporter/actions/workflows/ci.yml/badge.svg)](https://github.com/polarpoint-io/freshservice-exporter/actions/workflows/ci.yml)
[![CodeQL](https://github.com/polarpoint-io/freshservice-exporter/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/polarpoint-io/freshservice-exporter/actions/workflows/codeql-analysis.yml)
[![GHCR](https://img.shields.io/badge/ghcr.io-freshservice--exporter-blue?logo=github)](https://github.com/polarpoint-io/freshservice-exporter/pkgs/container/freshservice-exporter)
[![Helm](https://img.shields.io/badge/Helm-ghcr.io%2Fpolarpoint--io%2Fcharts-blue?logo=helm)](https://github.com/polarpoint-io/freshservice-exporter/pkgs/container/charts%2Ffreshservice-exporter)

> **PyPI**: `pip install freshservice-exporter` · **Image**: `ghcr.io/polarpoint-io/freshservice-exporter:latest` · **Chart**: `ghcr.io/polarpoint-io/charts/freshservice-exporter`

## Repository layout

```
├── exporter.py              # Prometheus collector entrypoint
├── client.py                # Freshservice API v2 client
├── metrics.py / dora.py     # Aggregation logic
├── charts/                  # Helm chart for Kubernetes
├── dashboards/              # Grafana dashboard JSON
├── examples/                # Prometheus / Grafana Agent scrape configs
├── scripts/scrape_once.py   # One-shot local test scrape
└── tests/
```

## Quick start

```bash
pip install -e .

export FRESHSERVICE_API_KEY=your_api_key
export FRESHSERVICE_DOMAIN=your_company.freshservice.com
export FRESHSERVICE_INCLUDE_STATS=true
export FRESHSERVICE_DORA_LOOKBACK_DAYS=30

freshservice-exporter
```

Metrics: `http://localhost:9192/metrics`

## Grafana query patterns

Use **sum/count pairs** for averages:

```promql
# Mean ticket resolution time (seconds)
sum(freshservice_ticket_resolution_duration_seconds_sum)
/
sum(freshservice_ticket_resolution_duration_seconds_count)

# Mean MTTR for incidents only (DORA)
freshservice_dora_mttr_seconds

# Deployment success rate
sum(freshservice_releases_completed_in_window_total)
/
(
  sum(freshservice_releases_completed_in_window_total)
  + sum(freshservice_releases_failed_in_window_total)
)

# Open ticket backlog by priority
sum by (priority) (freshservice_tickets_open_by_priority_total)
```

## Metric catalog

### Tickets

| Metric | Labels | Description |
|---|---|---|
| `freshservice_tickets_total` | — | Tickets in fetch scope |
| `freshservice_tickets_by_status_total` | `status` | Count by status |
| `freshservice_tickets_by_priority_total` | `priority` | Count by priority |
| `freshservice_tickets_by_type_total` | `type` | Incident, Service Request, … |
| `freshservice_tickets_by_group_total` | `group_id` | Assignment group |
| `freshservice_tickets_by_category_total` | `category` | Category |
| `freshservice_tickets_by_department_total` | `department_id` | Department |
| `freshservice_tickets_by_workspace_total` | `workspace_id` | Workspace |
| `freshservice_tickets_by_source_total` | `source` | email, portal, slack, … |
| `freshservice_tickets_by_impact_total` | `impact` | low / medium / high |
| `freshservice_tickets_by_status_priority_total` | `status`, `priority` | Cross-tab |
| `freshservice_tickets_by_type_status_total` | `type`, `status` | Cross-tab |
| `freshservice_tickets_open_by_priority_total` | `priority` | Open + pending only |
| `freshservice_tickets_open_age_bucket_total` | `bucket` | 1d, 3d, 7d, 30d, 90d, older |
| `freshservice_tickets_unassigned_open_total` | — | No responder |
| `freshservice_tickets_escalated_open_total` | — | Escalated |
| `freshservice_tickets_overdue_open_total` | — | Past `due_by` |
| `freshservice_tickets_first_response_overdue_open_total` | — | Past `fr_due_by` |
| `freshservice_tickets_spam_total` | — | Spam flag |
| `freshservice_tickets_resolved_in_window_total` | `type` | Resolved in lookback window |
| `freshservice_ticket_resolution_duration_seconds_sum` | `type`, `priority` | Resolution time sum |
| `freshservice_ticket_resolution_duration_seconds_count` | `type`, `priority` | Resolution time count |
| `freshservice_ticket_first_response_duration_seconds_sum` | `type`, `priority` | First response sum |
| `freshservice_ticket_first_response_duration_seconds_count` | `type`, `priority` | First response count |

### Changes

| Metric | Labels | Description |
|---|---|---|
| `freshservice_changes_total` | — | Changes in scope |
| `freshservice_changes_by_status_total` | `status` | Pipeline stage |
| `freshservice_changes_by_priority_total` | `priority` | Priority |
| `freshservice_changes_by_risk_total` | `risk` | Risk level |
| `freshservice_changes_by_type_total` | `change_type` | minor / standard / major / emergency |
| `freshservice_changes_by_group_total` | `group_id` | Group |
| `freshservice_changes_by_department_total` | `department_id` | Department |
| `freshservice_changes_by_approval_status_total` | `approval_status` | Approval state |
| `freshservice_changes_by_status_type_total` | `status`, `change_type` | Cross-tab |
| `freshservice_changes_by_status_risk_total` | `status`, `risk` | Cross-tab |
| `freshservice_changes_open_by_type_total` | `change_type` | Open pipeline |
| `freshservice_changes_open_age_bucket_total` | `bucket` | Age of open changes |
| `freshservice_changes_emergency_open_total` | — | Open emergency changes |
| `freshservice_changes_overdue_open_total` | — | Past `planned_end_date` |
| `freshservice_changes_closed_in_window_total` | `change_type` | Closed in lookback window |
| `freshservice_change_cycle_duration_seconds_sum` | `change_type` | created → closed sum |
| `freshservice_change_cycle_duration_seconds_count` | `change_type` | created → closed count |
| `freshservice_change_approval_to_close_duration_seconds_sum` | `change_type` | approval → close sum |
| `freshservice_change_approval_to_close_duration_seconds_count` | `change_type` | approval → close count |

### Releases (deployments)

| Metric | Labels | Description |
|---|---|---|
| `freshservice_releases_total` | — | Releases in scope |
| `freshservice_releases_by_status_total` | `status` | open, in_progress, completed, incomplete |
| `freshservice_releases_by_type_total` | `release_type` | minor / standard / major / emergency |
| `freshservice_releases_by_priority_total` | `priority` | Priority |
| `freshservice_releases_by_type_status_total` | `release_type`, `status` | Cross-tab |
| `freshservice_releases_open_by_type_total` | `release_type` | In-flight releases |
| `freshservice_releases_open_age_bucket_total` | `bucket` | Age of open releases |
| `freshservice_releases_overdue_open_total` | — | Past `planned_end_date` |
| `freshservice_releases_completed_in_window_total` | `release_type` | Successful deployments |
| `freshservice_releases_failed_in_window_total` | `release_type` | Failed (incomplete) deployments |
| `freshservice_release_work_duration_seconds_sum` | `release_type` | work_end − work_start sum |
| `freshservice_release_work_duration_seconds_count` | `release_type` | work_end − work_start count |

### Problems

| Metric | Labels | Description |
|---|---|---|
| `freshservice_problems_total` | — | Problems in scope |
| `freshservice_problems_by_status_total` | `status` | Status |
| `freshservice_problems_by_priority_total` | `priority` | Priority |
| `freshservice_problems_by_impact_total` | `impact` | Impact |
| `freshservice_problems_by_status_impact_total` | `status`, `impact` | Cross-tab |
| `freshservice_problems_known_error_total` | — | Known errors |
| `freshservice_problems_open_total` | — | Open problems |
| `freshservice_problems_open_age_bucket_total` | `bucket` | Age buckets |
| `freshservice_problems_overdue_open_total` | — | Past `due_by` |

### DORA

| Metric | Description |
|---|---|
| `freshservice_dora_mttr_seconds` | Mean time to restore (incidents) |
| `freshservice_dora_mttr_incident_count` | Sample size |
| `freshservice_dora_first_response_seconds` | Mean first response |
| `freshservice_dora_lead_time_seconds` | Mean change lead time |
| `freshservice_dora_deployment_frequency_per_day` | Releases per day |
| `freshservice_dora_change_failure_rate` | Failed / (success + failed) |
| `freshservice_dora_deployments_total` | `outcome=success\|failed\|in_progress` |
| `freshservice_dora_open_incidents_total` | Open incidents by priority |
| `freshservice_dora_lookback_days` | Configured window |

### Exporter diagnostics

| Metric | Description |
|---|---|
| `freshservice_exporter_last_scrape_timestamp` | Last scrape unix time |
| `freshservice_exporter_last_scrape_duration_seconds` | Scrape duration |
| `freshservice_exporter_last_scrape_successful` | 1 = OK |
| `freshservice_exporter_api_errors_total` | Cumulative errors |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `FRESHSERVICE_API_KEY` | required | API key |
| `FRESHSERVICE_DOMAIN` | required | `company.freshservice.com` |
| `EXPORTER_PORT` | `9192` | Metrics port |
| `SCRAPE_INTERVAL` | `300` | Seconds between API scrapes |
| `FRESHSERVICE_DORA_LOOKBACK_DAYS` | `30` | Window for DORA + resolved counts |
| `FRESHSERVICE_INCLUDE_STATS` | `true` | Embed stats (needed for durations) |
| `FRESHSERVICE_MTTR_TICKET_TYPES` | `Incident` | Ticket types for MTTR |
| `FRESHSERVICE_WORKSPACE_ID` | — | `0` = all workspaces |

## Development

```bash
make install
make test
make lint
make scrape    # requires .env with API credentials
```

## Publish to GitHub (polarpoint-io)

```bash
gh auth login

gh repo create polarpoint-io/freshservice-exporter --private --source=. --remote=origin
git push -u origin main
```

### Required GitHub secrets

Add these at **GitHub repo → Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `POL_GH_TOKEN` | PAT with `repo` + `write:packages` scope (semantic-release) |
| `PYPI_TOKEN` | PyPI API token for `freshservice-exporter` |

## Helm

```bash
helm registry login ghcr.io --username <github-user> --password <github-pat>

helm install freshservice-exporter oci://ghcr.io/polarpoint-io/charts/freshservice-exporter \
  --namespace monitoring --create-namespace \
  --set freshservice.apiKey=<API_KEY> \
  --set freshservice.domain=company.freshservice.com
```

Or install from the local chart during development:

```bash
helm install freshservice-exporter ./charts/freshservice-exporter \
  --namespace monitoring --create-namespace \
  --set freshservice.apiKey=<API_KEY> \
  --set freshservice.domain=company.freshservice.com
```

## License

MIT
