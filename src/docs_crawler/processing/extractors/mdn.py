"""MDN site fields: the docs section a page belongs to and when it was last modified."""

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

SECTION_DEPTH = 3  # "Web/JavaScript/Reference": deep enough to group pages, not per page
LAST_MODIFIED_SELECTOR = "p.article-footer__last-modified time[datetime]"


def extract_site_fields(html: str, url: str) -> dict[str, str]:
    """Return MDN's `section` (from the URL) and `last_modified` (from the page footer).

    A field is left out when the page does not have it, instead of being stored empty.
    """
    fields: dict[str, str] = {}
    section = _section(url)
    if section:
        fields["section"] = section
    last_modified = _last_modified(html)
    if last_modified:
        fields["last_modified"] = last_modified
    return fields


def _section(url: str) -> str:
    # /en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/map -> Web/JavaScript/Reference
    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    if "docs" not in segments:
        return ""
    parents = segments[segments.index("docs") + 1 : -1]  # the last segment is the page itself
    return "/".join(parents[:SECTION_DEPTH])


def _last_modified(html: str) -> str:
    time = BeautifulSoup(html, "lxml").select_one(LAST_MODIFIED_SELECTOR)
    return str(time["datetime"]).strip() if time is not None else ""
