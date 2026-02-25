"""Async client for the Hetzner Robot API (https://robot-ws.your-server.de).

Provides methods for listing and retrieving dedicated servers.  Uses HTTP
Basic Auth with credentials from application settings.

Note: The Robot API does **not** expose server metrics -- those are collected
by the lightweight InfraScope agent running on each dedicated server.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://robot-ws.your-server.de"
MAX_RETRIES = 3
INITIAL_BACKOFF_S = 1.0


class HetznerRobotError(Exception):
    """Raised when the Hetzner Robot API returns an unexpected error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Hetzner Robot API error {status_code}: {detail}")


class HetznerRobotClient:
    """Async wrapper around the Hetzner Robot REST API."""

    def __init__(
        self,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._user = user or settings.hetzner_robot_user
        self._password = password or settings.hetzner_robot_password
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle helpers ---------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                auth=httpx.BasicAuth(self._user, self._password),
                timeout=30.0,
                headers={"Accept": "application/json"},
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
    ) -> Any:
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
                    "Rate-limited by Hetzner Robot API (attempt %d/%d), "
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
                raise HetznerRobotError(response.status_code, detail)

            return response.json()

        raise HetznerRobotError(429, "Rate limit exceeded after max retries")

    # -- public API methods --------------------------------------------------

    async def list_servers(self) -> list[dict[str, Any]]:
        """Return all dedicated servers.

        Each item in the response is a dict with a ``server`` key containing
        the server details (``server_ip``, ``server_name``, ``product``,
        ``dc``, ``status``, etc.).
        """
        logger.info("Fetching all dedicated servers from Hetzner Robot API")
        data = await self._request("GET", "/server")

        # The Robot API returns a list of objects, each wrapping server data
        # under a "server" key:  [{"server": {...}}, ...]
        if isinstance(data, list):
            return [item.get("server", item) for item in data]
        return []

    async def get_server(self, server_ip: str) -> dict[str, Any]:
        """Return detailed information for a single dedicated server.

        Args:
            server_ip: The primary IPv4 address of the server.

        Returns:
            Raw server dict from the API including ``server_ip``,
            ``server_name``, ``product``, ``dc``, ``status``, ``paid_until``,
            ``traffic``, ``cancelled``, etc.
        """
        logger.info("Fetching dedicated server %s from Hetzner Robot API", server_ip)
        data = await self._request("GET", f"/server/{server_ip}")

        # Response wraps the data under a "server" key
        if isinstance(data, dict) and "server" in data:
            return data["server"]
        return data


# Module-level convenience instance
_default_client: HetznerRobotClient | None = None


def get_client() -> HetznerRobotClient:
    """Return the module-level singleton client."""
    global _default_client
    if _default_client is None:
        _default_client = HetznerRobotClient()
    return _default_client


async def list_servers() -> list[dict[str, Any]]:
    """Module-level shortcut: list all dedicated servers."""
    return await get_client().list_servers()


async def get_server(server_ip: str) -> dict[str, Any]:
    """Module-level shortcut: get a single dedicated server."""
    return await get_client().get_server(server_ip)
