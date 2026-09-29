"""Input validation / sanitisation helpers."""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from urllib.parse import urlparse, urlunparse

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InvalidURLError(ValueError):
    pass


def validate_url(url: str, allowed_hosts: tuple[str, ...] | None = None) -> str:
    """Validate an http(s) URL, reject private/loopback hosts, optionally restrict domains.

    Returns a normalised URL without fragment.
    """
    url = (url or "").strip()
    if len(url) > 2048:
        raise InvalidURLError("URL too long")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise InvalidURLError("Only http(s) URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise InvalidURLError("URL has no host")
    if parsed.username or parsed.password:
        raise InvalidURLError("Credentials in URLs are not allowed")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise InvalidURLError("Private addresses are not allowed")
    except ValueError:
        if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
            raise InvalidURLError("Local hosts are not allowed") from None
    if allowed_hosts and not any(host == h or host.endswith("." + h) for h in allowed_hosts):
        raise InvalidURLError(f"Host {host} not allowed (expected one of {', '.join(allowed_hosts)})")
    return urlunparse(parsed._replace(fragment=""))


def sanitize_text(value: str | None, max_len: int = 500) -> str | None:
    """Strip control characters, normalise unicode and cap the length of imported text."""
    if value is None:
        return None
    value = unicodedata.normalize("NFKC", str(value))
    value = _CONTROL.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max_len]
