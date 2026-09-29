"""Shared polite HTTP client: retries, exponential backoff, per-source rate limiting, robots.txt."""

from __future__ import annotations

import threading
import time
from urllib import robotparser
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class RateLimiter:
    """Simple blocking limiter: at most ``rate`` requests per second."""

    def __init__(self, rate: float) -> None:
        self.min_interval = 1.0 / rate if rate > 0 else 0.0
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            delay = self._last + self.min_interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


class SourceHTTPError(RuntimeError):
    """Raised when a source request fails after retries. Message is safe to log."""


class PoliteClient:
    def __init__(
        self,
        source: str,
        rate_per_second: float = 1.0,
        headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.source = source
        self.limiter = RateLimiter(rate_per_second)
        self.max_retries = max_retries
        base_headers = {"User-Agent": get_settings().http_user_agent, "Accept": "application/json"}
        base_headers.update(headers or {})
        self.client = httpx.Client(
            headers=base_headers, timeout=timeout, follow_redirects=True, transport=transport
        )

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        last_error: str = ""
        for attempt in range(self.max_retries + 1):
            self.limiter.wait()
            try:
                resp = self.client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}"
            else:
                if resp.status_code not in RETRY_STATUSES:
                    if resp.status_code >= 400:
                        raise SourceHTTPError(f"{self.source}: HTTP {resp.status_code} for {urlparse(url).path}")
                    return resp
                last_error = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    time.sleep(min(int(retry_after), 60))
            if attempt < self.max_retries:
                backoff = min(2**attempt, 30)
                log.warning("http_retry", source=self.source, attempt=attempt + 1, error=last_error,
                            backoff_s=backoff)
                time.sleep(backoff)
        raise SourceHTTPError(f"{self.source}: request failed after retries ({last_error})")

    def close(self) -> None:
        self.client.close()


_robots_cache: dict[str, tuple[float, robotparser.RobotFileParser | None]] = {}


def robots_allowed(url: str, user_agent: str | None = None, ttl_s: int = 6 * 3600) -> bool:
    """Return True only if robots.txt explicitly permits fetching ``url``.

    If robots.txt cannot be fetched we treat it as *not* allowed (conservative).
    """
    user_agent = user_agent or get_settings().http_user_agent
    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    cached = _robots_cache.get(root)
    if not cached or time.time() - cached[0] > ttl_s:
        rp: robotparser.RobotFileParser | None = robotparser.RobotFileParser()
        try:
            resp = httpx.get(f"{root}/robots.txt", headers={"User-Agent": user_agent}, timeout=10,
                             follow_redirects=True)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            elif resp.status_code in (401, 403):
                rp = None
            else:  # 404 etc. → standard semantics: everything allowed
                rp.parse([])
        except httpx.HTTPError:
            rp = None
        _robots_cache[root] = (time.time(), rp)
        cached = _robots_cache[root]
    rp = cached[1]
    return bool(rp and rp.can_fetch(user_agent, url))
