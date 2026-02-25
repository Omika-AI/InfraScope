"""Async client for the Hetzner Cloud API (https://api.hetzner.cloud/v1).

Provides methods for listing servers, fetching metrics, and listing server
types.  All network calls use httpx with Bearer token authentication and
automatic exponential-backoff retry on 429 rate-limit responses.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hetzner.cloud/v1"
MAX_RETRIES = 3
INITIAL_BACKOFF_S = 1.0


class HetznerCloudError(Exception):
    """Raised when the Hetzner Cloud API returns an unexpected error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Hetzner Cloud API error {status_code}: {detail}")


class HetznerCloudClient:
    """Async wrapper around the Hetzner Cloud REST API."""

    def __init__(self, token: str | None = None) -> None:
        self._token = token or settings.hetzner_cloud_api_token
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle helpers ---------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=self._headers(),
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- low-level request with retry ----------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue an HTTP request with exponential backoff on 429 responses."""
        client = await self._get_client()
        backoff = INITIAL_BACKOFF_S

        for attempt in range(1, MAX_RETRIES + 1):
            response = await client.request(method, path, params=params)

            if response.status_code == 429:
                retry_after = float(
                    response.headers.get("Retry-After", str(backoff))
                )
                logger.warning(
                    "Rate-limited by Hetzner Cloud API (attempt %d/%d), "
                    "retrying in %.1fs",
                    attempt,
                    MAX_RETRIES,
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                backoff *= 2
                continue

            if response.status_code >= 400:
                detail = response.text[:500]
                raise HetznerCloudError(response.status_code, detail)

            return response.json()

        # Exhausted all retries on 429
        raise HetznerCloudError(429, "Rate limit exceeded after max retries")

    # -- paginated GET helper ------------------------------------------------

    async def _get_all_pages(
        self,
        path: str,
        result_key: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated endpoint and merge items."""
        all_items: list[dict[str, Any]] = []
        page = 1
        per_page = 50
        base_params = dict(params) if params else {}

        while True:
            base_params["page"] = page
            base_params["per_page"] = per_page
            data = await self._request("GET", path, params=base_params)

            items = data.get(result_key, [])
            all_items.extend(items)

            # Hetzner uses meta.pagination for paging info
            meta = data.get("meta", {}).get("pagination", {})
            total_pages = meta.get("last_page", page)

            if page >= total_pages:
                break
            page += 1

        return all_items

    # -- public API methods --------------------------------------------------

    async def list_servers(self) -> list[dict[str, Any]]:
        """Return all cloud servers across all pages.

        Each item is the raw server dict from the Hetzner API, including
        fields like ``id``, ``name``, ``server_type``, ``datacenter``,
        ``public_net``, ``status``, ``labels``, etc.
        """
        logger.info("Fetching all cloud servers from Hetzner Cloud API")
        return await self._get_all_pages("/servers", "servers")

    async def get_server_metrics(
        self,
        server_id: int | str,
        metric_type: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Fetch metrics for a single server.

        Args:
            server_id: Hetzner server ID.
            metric_type: One of ``"cpu"``, ``"disk"``, ``"network"``.
            start: Start of the time window (UTC).
            end: End of the time window (UTC).

        Returns:
            Raw metrics dict from the API including ``metrics.timeseries``.
        """
        params = {
            "type": metric_type,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        logger.debug(
            "Fetching %s metrics for server %s (%s -> %s)",
            metric_type,
            server_id,
            start.isoformat(),
            end.isoformat(),
        )
        return await self._request(
            "GET", f"/servers/{server_id}/metrics", params=params
        )

    async def list_server_types(self) -> list[dict[str, Any]]:
        """Return all available Hetzner Cloud server types.

        Useful for mapping server type names to specs (cores, memory, disk)
        and pricing information.
        """
        logger.info("Fetching server types from Hetzner Cloud API")
        return await self._get_all_pages("/server_types", "server_types")


# Module-level convenience instance (lazily shares a single client)
_default_client: HetznerCloudClient | None = None


def get_client() -> HetznerCloudClient:
    """Return the module-level singleton client."""
    global _default_client
    if _default_client is None:
        _default_client = HetznerCloudClient()
    return _default_client


async def list_servers() -> list[dict[str, Any]]:
    """Module-level shortcut: list all cloud servers."""
    return await get_client().list_servers()


async def get_server_metrics(
    server_id: int | str,
    metric_type: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Module-level shortcut: get metrics for a server."""
    return await get_client().get_server_metrics(
        server_id, metric_type, start, end
    )


async def list_server_types() -> list[dict[str, Any]]:
    """Module-level shortcut: list all server types."""
    return await get_client().list_server_types()
