"""URL normalization: map every spelling of the same page to one canonical URL.

The crawler uses the canonical form as the key of the shared "seen" set and of the
`pages` table, so the same page is never fetched or stored twice.
"""

import re
from urllib.parse import SplitResult, parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})
DEFAULT_PORTS = {"http": 80, "https": 443}
TRACKING_PARAMS = frozenset({"fbclid", "gclid"})
TRACKING_PREFIXES = ("utm_",)

_DUPLICATE_SLASHES = re.compile(r"/{2,}")


class InvalidURLError(ValueError):
    """Raised for links the crawler must not follow (mailto:, javascript:, no host, ...)."""


def normalize_url(url: str, base: str | None = None) -> str:
    """Return the canonical form of `url`, resolving it against `base` if it is relative.

    Raises InvalidURLError if the result is not an absolute http(s) URL with a host.
    """
    cleaned = url.strip()
    absolute = urljoin(base, cleaned) if base else cleaned
    parts = urlsplit(absolute)

    scheme = parts.scheme.lower()
    if not scheme:
        raise InvalidURLError(f"Relative URL needs a base: {url!r}")
    if scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError(f"Unsupported scheme {scheme!r} in {url!r}")

    return urlunsplit(
        (
            scheme,
            _normalize_netloc(parts, scheme, url),
            _normalize_path(parts.path),
            _normalize_query(parts.query),
            "",  # fragments only point inside a page, so they never make a new page
        )
    )


def _normalize_netloc(parts: SplitResult, scheme: str, original: str) -> str:
    host = parts.hostname  # already lowercased; user:password@ is dropped on purpose
    if not host:
        raise InvalidURLError(f"Missing host in {original!r}")
    try:
        port = parts.port
    except ValueError as exc:
        raise InvalidURLError(f"Invalid port in {original!r}") from exc

    if ":" in host:  # IPv6 literals need their brackets back
        host = f"[{host}]"
    if port is None or port == DEFAULT_PORTS[scheme]:
        return host
    return f"{host}:{port}"


def _normalize_path(path: str) -> str:
    # Path case is kept: servers may treat /Web and /web as different pages.
    collapsed = _DUPLICATE_SLASHES.sub("/", path)
    return collapsed or "/"


def _normalize_query(query: str) -> str:
    pairs = parse_qsl(query, keep_blank_values=True)
    kept = [(key, value) for key, value in pairs if not _is_tracking_param(key)]
    return urlencode(sorted(kept))


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in TRACKING_PARAMS or lowered.startswith(TRACKING_PREFIXES)
