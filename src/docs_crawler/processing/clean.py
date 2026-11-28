"""HTML cleaning: turn a fetched page into a title and ordered content blocks."""

from typing import Literal

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PreformattedString, Tag
from pydantic import BaseModel, ConfigDict

from docs_crawler.processing.blocks import (
    Block,
    CodeBlock,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    TableBlock,
)

Site = Literal["mdn", "python_docs", "devdocs"]

# CSS selector of the element that holds the article on each site. Everything outside it
# (menus, sidebars, footers) is ignored. Checked against the saved fixtures.
CONTENT_SELECTORS: dict[Site, str] = {
    "mdn": "main#content",
    "python_docs": 'div.body[role="main"]',
    "devdocs": "div._page",
}

# Elements inside the content area that are never article text. Python docs put real
# footnotes in <aside class="footnote">, so those asides are kept.
NOISE_SELECTOR = ", ".join(
    [
        "script",
        "style",
        "noscript",
        "nav",
        "header",
        "footer",
        "aside:not(.footnote-list):not(.footnote)",
        "form",
        "iframe",
        "button",
        "svg",
        # MDN widgets (feedback buttons, compatibility table loader) live in <template>
        # shadow roots. CSS selectors do not look inside a <template>, so the whole
        # element must go, or its <style> text leaks into the blocks.
        "template",
        ".article-footer",  # MDN: "last modified on …" and "View this page on GitHub"
        "a.headerlink",  # Python docs: the "¶" permalink after headings and function names
    ]
)

# The title is read before noise is removed, so its "¶" permalink is stripped by hand.
PERMALINK_SIGN = "¶"

HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

# Tags that sit inside a line of text. Loose text and these tags are collected into one
# paragraph, so "Call <code>map()</code> on it" stays one sentence.
INLINE_TAGS = frozenset(
    {
        "a", "abbr", "b", "bdi", "bdo", "br", "cite", "code", "data", "del", "dfn", "em", "i",
        "img", "ins", "kbd", "mark", "q", "s", "samp", "small", "span", "strong", "sub",
        "sup", "time", "u", "var", "wbr",
    }
)  # fmt: skip


class CleanedPage(BaseModel):
    """The result of cleaning one page, before it is validated as a full document.

    `title` may be empty here: the document schema (not the cleaner) decides that an empty
    title is invalid, so the page is rejected with a readable reason instead of crashing.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    blocks: list[Block]


class ContentNotFoundError(ValueError):
    """Raised when a page has no element matching its site's content selector."""


def find_content_area(soup: BeautifulSoup, site: Site) -> Tag:
    """Return the element that holds the article, or raise ContentNotFoundError.

    A page without it is broken or has a layout we do not know, so failing loudly is
    better than saving an empty document.
    """
    selector = CONTENT_SELECTORS[site]
    content = soup.select_one(selector)
    if content is None:
        raise ContentNotFoundError(f"No content area {selector!r} found for site {site!r}")
    return content


def clean_html(html: str, site: Site) -> CleanedPage:
    """Turn a page's HTML into its title and the article's blocks, in page order.

    Raises ContentNotFoundError if the page has no content area for `site`.
    """
    soup = BeautifulSoup(html, "lxml")
    content = find_content_area(soup, site)
    title = extract_title(soup, content)
    remove_noise(content)
    return CleanedPage(title=title, blocks=_BlockBuilder().build(content))


def remove_noise(content: Tag) -> None:
    """Delete scripts, styles, menus, sidebars, buttons and similar elements in place."""
    for element in content.select(NOISE_SELECTOR):
        if not element.decomposed:  # already gone if an outer noise element was removed
            element.decompose()


def extract_title(soup: BeautifulSoup, content: Tag) -> str:
    """Return the first <h1> in the article, else the page <title>, else ""."""
    heading = content.find("h1")
    source = heading if heading is not None else soup.title
    if source is None:
        return ""
    return normalize_text(source.get_text().replace(PERMALINK_SIGN, ""))


def code_language(pre: Tag) -> str | None:
    """Return the language of a <pre> code sample, or None if the page does not say.

    Each site marks it differently (checked in the fixtures):
    DevDocs `<pre class="language-js">`, MDN `<pre class="brush: js">`, and Python docs
    `<div class="highlight-python3"><div class="highlight"><pre>` (on a wrapper).
    """
    classes = pre.get_attribute_list("class")
    for index, name in enumerate(classes):
        if name.startswith("language-"):
            return name.removeprefix("language-").lower() or None
        if name == "brush:" and index + 1 < len(classes):
            return classes[index + 1].lower()
    wrapper = pre.find_parent(
        class_=lambda name: name is not None and name.startswith("highlight-")
    )
    if wrapper is not None:
        for name in wrapper.get_attribute_list("class"):
            if name.startswith("highlight-"):
                return name.removeprefix("highlight-").lower() or None
    return None


def normalize_text(text: str) -> str:
    """Collapse every run of whitespace into one space and trim the ends."""
    return " ".join(text.split())


def element_text(element: Tag) -> str:
    """Return the element's text with a space wherever a non-inline tag starts.

    `get_text()` alone glues "<li><p>a</p><p>b</p></li>" into "ab"; adding a space at each
    block boundary keeps the words apart, and inline tags still join without a gap.
    """
    pieces: list[str] = []
    for node in element.descendants:
        if isinstance(node, Tag):
            if node.name not in INLINE_TAGS or node.name == "br":
                pieces.append(" ")
        elif isinstance(node, NavigableString) and not isinstance(node, PreformattedString):
            pieces.append(str(node))  # PreformattedString = comments, CDATA, doctype
    return "".join(pieces)


class _BlockBuilder:
    """Walks the content area once, top to bottom, and collects blocks in order."""

    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self._open_headings: list[tuple[int, str]] = []  # (level, text) from h1 down
        self._loose_text: list[str] = []

    def build(self, content: Tag) -> list[Block]:
        self._walk(content)
        return self.blocks

    def _walk(self, container: Tag) -> None:
        for child in container.children:
            if isinstance(child, Tag):
                self._visit(child)
            elif isinstance(child, NavigableString) and not isinstance(child, PreformattedString):
                self._loose_text.append(str(child))
        self._flush_loose_text()

    def _visit(self, element: Tag) -> None:
        if element.name in INLINE_TAGS:
            # <br> has no text of its own, but it still separates two words
            self._loose_text.append(" " if element.name == "br" else element_text(element))
            return
        self._flush_loose_text()
        if element.name in HEADING_LEVELS:
            self._add_heading(element)
        elif element.name in ("p", "dt"):  # dt = the term in a definition list (MDN parameters)
            self._add_paragraph(element_text(element))
        elif element.name in ("ul", "ol"):
            self._add_list(element)
        elif element.name == "pre":
            self._add_code(element)
        elif element.name == "table":
            self._add_table(element)
        else:  # a wrapper such as div, section or dd: look inside it
            self._walk(element)

    def _flush_loose_text(self) -> None:
        if self._loose_text:
            self._add_paragraph("".join(self._loose_text))
            self._loose_text = []

    def _add_heading(self, element: Tag) -> None:
        text = normalize_text(element_text(element))
        if not text:
            return
        level = HEADING_LEVELS[element.name]
        # A new heading closes every open heading at its level or deeper: after h2 "A" and
        # h3 "B", an h2 "C" leaves only the h1 open. The heading's own path is its parents.
        while self._open_headings and self._open_headings[-1][0] >= level:
            self._open_headings.pop()
        self.blocks.append(HeadingBlock(heading_path=self._path(), level=level, text=text))
        self._open_headings.append((level, text))

    def _add_paragraph(self, raw_text: str) -> None:
        text = normalize_text(raw_text)
        if text:
            self.blocks.append(ParagraphBlock(heading_path=self._path(), text=text))

    def _add_list(self, element: Tag) -> None:
        items = [normalize_text(element_text(li)) for li in element.find_all("li", recursive=False)]
        items = [item for item in items if item]
        if items:
            ordered = element.name == "ol"
            self.blocks.append(ListBlock(heading_path=self._path(), ordered=ordered, items=items))

    def _add_code(self, element: Tag) -> None:
        text = element.get_text().strip("\n")  # keep indentation: whitespace matters in code
        if text.strip():
            language = code_language(element)
            self.blocks.append(CodeBlock(heading_path=self._path(), language=language, text=text))

    def _add_table(self, element: Tag) -> None:
        # Only this table's own rows: a table nested in a cell is part of that cell's text.
        own_rows = [row for row in element.find_all("tr") if row.find_parent("table") is element]
        headers: list[str] = []
        if own_rows and _is_header_row(own_rows[0]):
            headers = _row_cells(own_rows.pop(0))
        rows = [cells for cells in map(_row_cells, own_rows) if any(cells)]
        if rows:
            caption = element.find("caption", recursive=False)
            caption_text = normalize_text(element_text(caption)) if caption is not None else ""
            self.blocks.append(
                TableBlock(
                    heading_path=self._path(),
                    caption=caption_text or None,
                    headers=headers,
                    rows=rows,
                )
            )

    def _path(self) -> list[str]:
        return [text for _, text in self._open_headings]


def _row_cells(row: Tag) -> list[str]:
    return [
        normalize_text(element_text(cell)) for cell in row.find_all(["th", "td"], recursive=False)
    ]


def _is_header_row(row: Tag) -> bool:
    """A header row sits in <thead>, or (without <thead>) has only <th> cells."""
    if row.find_parent("thead") is not None:
        return True
    cells = row.find_all(["th", "td"], recursive=False)
    return bool(cells) and all(cell.name == "th" for cell in cells)
