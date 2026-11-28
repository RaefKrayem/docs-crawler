"""Change detection: decide what a re-crawl means for the stored versions of a page."""

from enum import StrEnum

NOT_MODIFIED = 304
GONE_STATUSES = frozenset({404, 410})


class ChangeDecision(StrEnum):
    NEW = "new"  # first time we store this page -> version 1
    NOT_MODIFIED = "not_modified"  # the server said 304: nothing was downloaded
    UNCHANGED = "unchanged"  # downloaded, but the cleaned content hash is the same
    CHANGED = "changed"  # different hash -> store a new version, keep the old ones
    REMOVED = "removed"  # 404/410 -> mark the page removed, never delete it


def conditional_headers(etag: str | None, last_modified: str | None) -> dict[str, str]:
    """Return the headers that let the server answer "304 Not Modified" on a re-crawl.

    `etag` and `last_modified` are the ETag and Last-Modified values the server sent with
    the previous fetch. Missing or blank values are left out.
    """
    headers: dict[str, str] = {}
    if etag and etag.strip():
        headers["If-None-Match"] = etag.strip()
    if last_modified and last_modified.strip():
        headers["If-Modified-Since"] = last_modified.strip()
    return headers


def decide(status: int, new_hash: str | None, previous_hash: str | None) -> ChangeDecision:
    """Decide what to do with a fetched page.

    `new_hash` is the content hash of the page just fetched (None when nothing was
    downloaded); `previous_hash` is the hash of its latest stored version (None if the
    page was never stored). Only 2xx, 304, 404 and 410 are content answers: anything else
    (429, 5xx, ...) is a failed fetch for the retry policy, so it raises ValueError.
    """
    if status in GONE_STATUSES:
        return ChangeDecision.REMOVED
    if status == NOT_MODIFIED:
        if previous_hash is None:
            raise ValueError("304 Not Modified without a stored version to compare with")
        return ChangeDecision.NOT_MODIFIED
    if not 200 <= status < 300:
        raise ValueError(f"HTTP {status} is not a content answer; retry or fail the fetch")
    if new_hash is None:
        raise ValueError(f"HTTP {status} needs the hash of the downloaded page")
    if previous_hash is None:
        return ChangeDecision.NEW
    if new_hash == previous_hash:
        return ChangeDecision.UNCHANGED
    return ChangeDecision.CHANGED
