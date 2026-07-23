"""Prometheus metric emission helpers."""

from __future__ import annotations

from typing import Any, Iterable

from prometheus_client.core import GaugeMetricFamily


def gauge(name: str, description: str, value: float) -> GaugeMetricFamily:
    m = GaugeMetricFamily(name, description)
    m.add_metric([], value)
    return m


def labeled_gauge(
    name: str,
    description: str,
    label_names: list[str],
    data: dict[Any, int | float],
) -> GaugeMetricFamily:
    m = GaugeMetricFamily(name, description, labels=label_names)
    for key, value in data.items():
        labels = [key] if isinstance(key, str) else list(key)
        m.add_metric(labels, value)
    return m


def sum_count_pair(
    prefix: str,
    description: str,
    label_names: list[str],
    sums: dict[Any, float],
    counts: dict[Any, int],
) -> Iterable[GaugeMetricFamily]:
    sum_metric = GaugeMetricFamily(f"{prefix}_sum", f"{description} (sum)", labels=label_names)
    count_metric = GaugeMetricFamily(f"{prefix}_count", f"{description} (count)", labels=label_names)
    for key in set(sums) | set(counts):
        labels = [key] if isinstance(key, str) else list(key)
        if key in sums:
            sum_metric.add_metric(labels, sums[key])
        if key in counts:
            count_metric.add_metric(labels, counts[key])
    yield sum_metric
    yield count_metric
