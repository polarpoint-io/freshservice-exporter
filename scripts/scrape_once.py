"""Run a single metrics scrape and print results (for local testing)."""

from __future__ import annotations

import os
import sys

from prometheus_client import CollectorRegistry, write_to_textfile

from client import FreshserviceClient
from exporter import FreshserviceCollector, _load_config


def main() -> int:
    missing = [k for k in ("FRESHSERVICE_API_KEY", "FRESHSERVICE_DOMAIN") if not os.environ.get(k)]
    if missing:
        print("Missing required environment variables:", ", ".join(missing), file=sys.stderr)
        print("Copy .env.example to .env and fill in your Freshservice credentials.", file=sys.stderr)
        return 1

    config = _load_config()
    client = FreshserviceClient.from_env()
    collector = FreshserviceCollector(client, config)

    registry = CollectorRegistry()
    registry.register(collector)

    output_path = os.environ.get("SCRAPE_OUTPUT", "/tmp/freshservice-exporter.prom")
    write_to_textfile(output_path, registry)

    with open(output_path, encoding="utf-8") as fh:
        lines = [line for line in fh if line.startswith("freshservice_") and not line.startswith("#")]

    metric_names = sorted({line.split("{")[0].split(" ")[0] for line in lines})
    print(f"Scrape OK — wrote {len(lines)} metric lines to {output_path}")
    print(f"Unique metric families: {len(metric_names)}")
    print()
    print("Sample metrics:")
    for name in metric_names[:15]:
        sample = next(line.strip() for line in lines if line.startswith(name))
        print(f"  {sample}")
    if len(metric_names) > 15:
        print(f"  … and {len(metric_names) - 15} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
