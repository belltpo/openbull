"""Trustworthy client-IP resolution.

``X-Forwarded-For`` and ``X-Real-IP`` are set by *clients* as easily as by
proxies, and nginx's ``$proxy_add_x_forwarded_for`` **appends** to whatever
already arrived rather than replacing it. The leftmost XFF entry is therefore
fully attacker-controlled on the shipped deployment.

The app previously read ``X-Forwarded-For.split(",")[0]`` unconditionally in
two places:

* ``backend.routers.strategy_webhook`` — feeding the per-strategy webhook IP
  allow-list, so one header defeated that control outright;
* ``backend.middleware_api_log`` — so the ``client_ip`` recorded against
  every logged trade could be forged.

Here the headers are honoured only when the *immediate peer* is a configured
trusted proxy, and the rightmost untrusted entry is taken (the last hop that
our own trusted infrastructure appended) rather than the leftmost.

With ``TRUSTED_PROXY_IPS`` empty, forwarded headers are ignored entirely and
the socket peer is always used.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache

from starlette.requests import HTTPConnection

from backend.config import get_settings

_MAX_IP_LEN = 64


@lru_cache(maxsize=1)
def _trusted() -> tuple[set[str], tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]]:
    """Parse TRUSTED_PROXY_IPS once into literal hosts and CIDR networks."""
    literals: set[str] = set()
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in get_settings().trusted_proxy_ip_list:
        if "/" in entry:
            try:
                networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                continue
        else:
            literals.add(entry)
    return literals, tuple(networks)


def _is_trusted_peer(peer: str | None) -> bool:
    if not peer:
        # Unix-socket peers have no address. uvicorn runs behind a UDS in the
        # shipped systemd unit, and only our own nginx can connect to it, so
        # treat that as trusted when any proxy is configured at all.
        return bool(_trusted()[0] or _trusted()[1])
    literals, networks = _trusted()
    if peer in literals:
        return True
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def _valid(candidate: str) -> str | None:
    candidate = candidate.strip()
    if not candidate or len(candidate) > _MAX_IP_LEN:
        return None
    # Strip an "[::1]:1234" / "1.2.3.4:1234" style port if present.
    if candidate.startswith("["):
        candidate = candidate[1:].split("]", 1)[0]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def client_ip(conn: HTTPConnection) -> str | None:
    """Best available client IP for logging, allow-lists and rate limiting."""
    peer = conn.client.host if conn.client else None

    if not _is_trusted_peer(peer):
        # Untrusted peer: it *is* the client. Ignore anything it claims.
        return _valid(peer) if peer else None

    forwarded = conn.headers.get("x-forwarded-for")
    if forwarded:
        # Rightmost entry is the one our trusted proxy appended; everything
        # to the left of it may have been supplied by the caller.
        for raw in reversed(forwarded.split(",")):
            found = _valid(raw)
            if found:
                return found

    real = conn.headers.get("x-real-ip")
    if real:
        found = _valid(real)
        if found:
            return found

    return _valid(peer) if peer else None


def reset_cache() -> None:
    """Test hook — drop the parsed TRUSTED_PROXY_IPS cache."""
    _trusted.cache_clear()


__all__ = ["client_ip", "reset_cache"]
