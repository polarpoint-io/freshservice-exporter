"""Freshservice API v2 client with pagination.

The unofficial ``freshservice-sdk-python`` package only supports CRUD on
individual resources by ID.  This client uses the same authentication scheme
(Basic auth with the API key) and exposes list endpoints needed for metrics.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

from requests import Response, Session

log = logging.getLogger("freshservice_exporter.client")

UNKNOWN = "unknown"


class FreshserviceError(Exception):
    """Raised when the Freshservice API returns a non-success response."""


class FreshserviceClient:
    def __init__(
        self,
        api_key: str,
        domain: str,
        *,
        per_page: int = 100,
        timeout: float = 30.0,
    ) -> None:
        self.per_page = max(1, min(per_page, 100))
        self.timeout = timeout
        self.session: Session = Session()
        self.session.auth = (api_key, "X")
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        domain = domain.removeprefix("https://").removeprefix("http://").rstrip("/")
        self.base_url = f"https://{domain}/api/v2/"

    @classmethod
    def from_env(cls) -> FreshserviceClient:
        api_key = os.environ["FRESHSERVICE_API_KEY"]
        domain = os.environ["FRESHSERVICE_DOMAIN"]
        per_page = int(os.environ.get("FRESHSERVICE_PER_PAGE", "100"))
        return cls(api_key=api_key, domain=domain, per_page=per_page)

    def _request(self, method: str, path: str, **kwargs: Any) -> Response:
        url = path if path.startswith("http") else f"{self.base_url}{path.lstrip('/')}"
        response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        if not 200 <= response.status_code <= 299:
            raise FreshserviceError(
                f"{method} {url} failed with HTTP {response.status_code}: {response.text[:500]}"
            )
        return response

    def _next_page(self, response: Response) -> str | None:
        link = response.headers.get("Link", "")
        for part in link.split(","):
            section = part.strip()
            if 'rel="next"' in section:
                start = section.find("<") + 1
                end = section.find(">")
                if start > 0 and end > start:
                    return section[start:end]
        return None

    def paginate(
        self,
        resource_key: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        query = dict(params or {})
        if "per_page" not in query:
            query["per_page"] = self.per_page

        next_url: str | None = path
        page = 1
        while next_url:
            if next_url.startswith("http"):
                response = self._request("GET", next_url)
            else:
                page_params = dict(query)
                if "page" not in page_params:
                    page_params["page"] = page
                response = self._request("GET", next_url, params=page_params)

            payload = response.json()
            items = payload.get(resource_key, [])
            if not isinstance(items, list):
                raise FreshserviceError(
                    f"Expected list at key '{resource_key}' in response from {next_url}"
                )

            yield from items

            next_url = self._next_page(response)
            if next_url:
                parsed = urlparse(next_url)
                page_qs = parse_qs(parsed.query)
                if "page" in page_qs and page_qs["page"]:
                    page = int(page_qs["page"][0])
                else:
                    page += 1
            else:
                if len(items) >= query.get("per_page", self.per_page):
                    page += 1
                    next_url = path
                    query["page"] = page
                    if len(items) == 0:
                        break
                else:
                    break

    def list_tickets(self, **params: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate("tickets", "tickets", params=params)

    def list_changes(self, **params: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate("changes", "changes", params=params)

    def list_problems(self, **params: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate("problems", "problems", params=params)

    def list_assets(self, **params: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate("assets", "assets", params=params)

    def list_releases(self, **params: Any) -> Iterator[dict[str, Any]]:
        yield from self.paginate("releases", "releases", params=params)

    def collect_list(self, list_fn, **params: Any) -> list[dict[str, Any]]:
        return list(list_fn(**params))
