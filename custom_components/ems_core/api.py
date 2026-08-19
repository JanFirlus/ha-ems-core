"""Dünner async HTTP-Client für die EMS-Core-API."""
from __future__ import annotations

from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=15)
HEALTH_TIMEOUT = aiohttp.ClientTimeout(total=10)


class EMSApiError(Exception):
    """Allgemeiner Fehler beim Zugriff auf die EMS-Core-API."""


class EMSAuthError(EMSApiError):
    """Login fehlgeschlagen (falsche Zugangsdaten)."""


class EMSApiClient:
    """Kapselt Login, Token-Refresh und GET-Zugriffe auf EMS-Core.

    Reagiert reaktiv auf abgelaufene Tokens (JWT läuft nach
    access_token_expire_minutes ab, Default 30min, siehe
    ems-core/app/config.py im ems-stack-Repo) statt den Ablauf proaktiv zu
    verfolgen: bei 401 einmal neu einloggen und die Anfrage wiederholen.
    """

    def __init__(self, session: aiohttp.ClientSession, host: str, email: str, password: str) -> None:
        self._session = session
        self._base_url = host.rstrip("/")
        self._email = email
        self._password = password
        self._token: str | None = None

    async def health(self) -> bool:
        try:
            async with self._session.get(f"{self._base_url}/api/v1/health", timeout=HEALTH_TIMEOUT) as resp:
                return resp.status == 200
        except aiohttp.ClientError as exc:
            raise EMSApiError(f"EMS-Core nicht erreichbar: {exc}") from exc

    async def login(self) -> None:
        payload = {"email": self._email, "password": self._password}
        try:
            async with self._session.post(
                f"{self._base_url}/api/v1/auth/login", json=payload, timeout=TIMEOUT
            ) as resp:
                if resp.status == 401:
                    raise EMSAuthError("E-Mail oder Passwort falsch")
                resp.raise_for_status()
                data = await resp.json()
        except aiohttp.ClientError as exc:
            raise EMSApiError(f"EMS-Core nicht erreichbar: {exc}") from exc
        self._token = data["access_token"]

    async def _get(self, path: str) -> Any:
        if self._token is None:
            await self.login()

        try:
            async with self._session.get(
                f"{self._base_url}{path}", headers=self._auth_headers(), timeout=TIMEOUT
            ) as resp:
                if resp.status == 401:
                    await self.login()
                    async with self._session.get(
                        f"{self._base_url}{path}", headers=self._auth_headers(), timeout=TIMEOUT
                    ) as retry_resp:
                        retry_resp.raise_for_status()
                        return await retry_resp.json()
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as exc:
            raise EMSApiError(f"EMS-Core nicht erreichbar: {exc}") from exc

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def get_devices(self) -> list[dict]:
        return await self._get("/api/v1/devices")

    async def get_status(self) -> list[dict]:
        return await self._get("/api/v1/status")

    async def get_energyflow(self) -> dict:
        return await self._get("/api/v1/energyflow/status")

    async def get_loadmanagement(self) -> dict:
        return await self._get("/api/v1/loadmanagement/status")
