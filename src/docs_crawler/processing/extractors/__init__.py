"""Site-specific fields: one extractor per site, all with the same signature."""

from collections.abc import Callable

from docs_crawler.processing.clean import Site
from docs_crawler.processing.extractors import devdocs, mdn, python_docs

Extractor = Callable[[str, str], dict[str, str]]  # (html, url) -> fields

EXTRACTORS: dict[Site, Extractor] = {
    "mdn": mdn.extract_site_fields,
    "python_docs": python_docs.extract_site_fields,
    "devdocs": devdocs.extract_site_fields,
}


def extract_site_fields(site: Site, html: str, url: str) -> dict[str, str]:
    """Run the extractor of `site` on one page."""
    return EXTRACTORS[site](html, url)
