"""Python docs site fields: the module a page documents and the docs version."""

import re

from bs4 import BeautifulSoup

# The page <title> ends with "— Python 3.15.2 documentation"
DOCS_VERSION = re.compile(r"\bPython (\d+(?:\.\d+)+\w*) documentation\b")


def extract_site_fields(html: str, url: str) -> dict[str, str]:
    """Return `module` (only on module pages) and `docs_version` (from the page title).

    `url` is unused: everything comes from the page. It is accepted so every site's
    extractor has the same signature. A field the page does not have is left out.
    """
    soup = BeautifulSoup(html, "lxml")
    fields: dict[str, str] = {}
    # json.html documents "json" and then "json.tool"; the first one is the page's module
    module_section = soup.select_one('section[id^="module-"]')
    if module_section is not None:
        fields["module"] = str(module_section["id"]).removeprefix("module-")
    title = soup.title.get_text() if soup.title is not None else ""
    version = DOCS_VERSION.search(title)
    if version is not None:
        fields["docs_version"] = version.group(1)
    return fields
