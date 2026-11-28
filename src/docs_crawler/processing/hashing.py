"""Content hash: a fingerprint of a page's cleaned content, used to detect changes."""

import hashlib
import json

from docs_crawler.processing.blocks import Block


def content_hash(title: str, blocks: list[Block]) -> str:
    """Return the SHA-256 of the title and blocks as 64 lowercase hex characters.

    The hash covers the *cleaned* content, not the raw HTML, so scripts, ads, menus and
    whitespace changes do not count as a change. It is computed from JSON with sorted
    keys and fixed separators, so the same content always gives the same hash.
    """
    canonical = json.dumps(
        {"title": title, "blocks": [block.model_dump(mode="json") for block in blocks]},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
