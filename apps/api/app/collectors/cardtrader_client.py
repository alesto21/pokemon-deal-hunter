"""CardTrader API v2 client (https://www.cardtrader.com/docs/api/full/reference).

Only documented endpoints are used: /info, /games, /categories, /expansions,
/blueprints/export and /marketplace/products. A mock client with deterministic
sample data is used when no API token is configured.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.core.config import get_settings
from app.core.http import PoliteClient


class CardTraderAPI(Protocol):
    is_mock: bool

    def info(self) -> dict[str, Any]: ...
    def games(self) -> list[dict[str, Any]]: ...
    def categories(self, game_id: int) -> list[dict[str, Any]]: ...
    def expansions(self) -> list[dict[str, Any]]: ...
    def blueprints(self, expansion_id: int) -> list[dict[str, Any]]: ...
    def marketplace_products(self, expansion_id: int | None = None, blueprint_id: int | None = None,
                             language: str | None = None) -> dict[str, list[dict[str, Any]]]: ...


class CardTraderClient:
    is_mock = False

    def __init__(self, token: str, base_url: str, rate_per_second: float = 2.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = PoliteClient("cardtrader", rate_per_second,
                                 headers={"Authorization": f"Bearer {token}"}, transport=transport)

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self.http.get(f"{self.base_url}{path}", params=params).json()

    def info(self) -> dict[str, Any]:
        return self._get("/info")

    def games(self) -> list[dict[str, Any]]:
        data = self._get("/games")
        return data.get("array", data) if isinstance(data, dict) else data

    def categories(self, game_id: int) -> list[dict[str, Any]]:
        return self._get("/categories", {"game_id": game_id})

    def expansions(self) -> list[dict[str, Any]]:
        return self._get("/expansions")

    def blueprints(self, expansion_id: int) -> list[dict[str, Any]]:
        return self._get("/blueprints/export", {"expansion_id": expansion_id})

    def marketplace_products(self, expansion_id: int | None = None, blueprint_id: int | None = None,
                             language: str | None = None) -> dict[str, list[dict[str, Any]]]:
        if not expansion_id and not blueprint_id:
            raise ValueError("expansion_id or blueprint_id is required")
        params: dict[str, Any] = {"expansion_id": expansion_id} if expansion_id else {"blueprint_id": blueprint_id}
        if language:
            params["language"] = language
        return self._get("/marketplace/products", params)

    def close(self) -> None:
        self.http.close()


def get_cardtrader_client(rate_per_second: float = 2.0) -> CardTraderAPI:
    s = get_settings()
    if s.cardtrader_is_mock:
        from app.collectors.cardtrader_mock import MockCardTraderClient

        return MockCardTraderClient()
    assert s.cardtrader_api_token is not None
    return CardTraderClient(s.cardtrader_api_token.get_secret_value(), s.cardtrader_base_url, rate_per_second)
