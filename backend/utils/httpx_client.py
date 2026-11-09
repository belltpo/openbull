import httpx

_client: httpx.Client | None = None


def get_httpx_client() -> httpx.Client:
    global _client
    if _client is None:
        # follow_redirects stays on (some broker endpoints redirect), but is
        # bounded: broker calls carry Authorization / api-key headers, and an
        # unbounded redirect chain is both a credential-forwarding risk and a
        # request-amplification one. httpx drops auth headers on cross-origin
        # redirects; the cap limits the rest.
        _client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            max_redirects=5,
        )
    return _client


def close_httpx_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None
