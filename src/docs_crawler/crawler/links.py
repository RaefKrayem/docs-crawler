"""Link extraction: the links a page's article points to, as canonical URLs.

The crawler stores these as (source page, target URL, link text) and later follows the
in-scope ones. Only links inside the article count: menus and sidebars link to the whole
site and say nothing about the page.
"""

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict

from docs_crawler.crawler.urls import InvalidURLError, normalize_url
from docs_crawler.processing.clean import (
    Site,
    element_text,
    find_content_area,
    normalize_text,
    remove_noise,
)


class Link(BaseModel):
    """One link from a page's article. `text` is empty for links without text (images)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_url: str
    text: str


def extract_links(html: str, page_url: str, site: Site) -> list[Link]:
    """Return the article's links in page order, with canonical target URLs.

    `page_url` must be the URL the page was finally served from (after redirects), because
    relative links are resolved against it. Links that cannot be crawled (mailto:,
    javascript:, ...) and links back to the page itself (#section anchors) are skipped;
    the same target with the same text is kept once.

    Raises ContentNotFoundError if the page has no content area for `site`.
    """
    soup = BeautifulSoup(html, "lxml")
    content = find_content_area(soup, site)
    remove_noise(content)
    page = normalize_url(page_url)

    links: list[Link] = []
    seen: set[Link] = set()
    for anchor in content.find_all("a", href=True):
        try:
            target = normalize_url(str(anchor["href"]), base=page)
        except InvalidURLError:
            continue
        link = Link(target_url=target, text=normalize_text(element_text(anchor)))
        if target != page and link not in seen:
            seen.add(link)
            links.append(link)
    return links
