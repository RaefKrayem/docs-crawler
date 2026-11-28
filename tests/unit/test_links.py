from pathlib import Path

import pytest

from docs_crawler.crawler.links import Link, extract_links
from docs_crawler.processing.clean import ContentNotFoundError

FIXTURES = Path(__file__).parent.parent / "fixtures" / "html"
PAGE = "https://docs.python.org/3/library/json.html"


def links_in(article: str, outside: str = "") -> list[Link]:
    """Extract links from a small Python-docs-style page."""
    html = f'<html><body>{outside}<div class="body" role="main">{article}</div></body></html>'
    return extract_links(html, PAGE, "python_docs")


def test_relative_link_is_resolved_against_the_page() -> None:
    assert links_in('<a href="../library/pickle.html">pickle</a>') == [
        Link(target_url="https://docs.python.org/3/library/pickle.html", text="pickle")
    ]


def test_target_is_canonical() -> None:
    [link] = links_in(
        '<a href="HTTPS://Docs.Python.org/3/library/os.html?utm_source=x#path">os</a>'
    )
    assert link.target_url == "https://docs.python.org/3/library/os.html"


def test_fragment_keeps_link_to_another_page() -> None:
    [link] = links_in('<a href="pickle.html#pickle.dumps">dumps()</a>')
    assert link.target_url == "https://docs.python.org/3/library/pickle.html"


@pytest.mark.parametrize(
    "href",
    [
        pytest.param("#basic-usage", id="same-page-anchor"),
        pytest.param("json.html#json.dumps", id="same-page-by-name"),
        pytest.param("", id="empty-href"),
    ],
)
def test_links_back_to_the_page_itself_are_skipped(href: str) -> None:
    assert links_in(f'<a href="{href}">here</a>') == []


@pytest.mark.parametrize(
    "href",
    [
        pytest.param("mailto:docs@python.org", id="mailto"),
        pytest.param("javascript:void(0)", id="javascript"),
        pytest.param("ftp://ftp.python.org/pub", id="ftp"),
    ],
)
def test_links_that_cannot_be_crawled_are_skipped(href: str) -> None:
    assert links_in(f'<a href="{href}">x</a>') == []


def test_anchor_without_href_is_skipped() -> None:
    assert links_in('<a id="top">Top</a>') == []


def test_same_target_and_text_is_kept_once_in_page_order() -> None:
    links = links_in(
        '<a href="os.html">os</a><a href="sys.html">sys</a>'
        '<a href="os.html#x">os</a><a href="os.html">the os module</a>'
    )
    assert links == [
        Link(target_url="https://docs.python.org/3/library/os.html", text="os"),
        Link(target_url="https://docs.python.org/3/library/sys.html", text="sys"),
        Link(target_url="https://docs.python.org/3/library/os.html", text="the os module"),
    ]


def test_link_text_whitespace_is_collapsed() -> None:
    [link] = links_in('<a href="os.html">  the \n <code>os</code>\n module </a>')
    assert link.text == "the os module"


def test_link_without_text_keeps_empty_text() -> None:
    [link] = links_in('<a href="os.html"><img src="logo.png" alt="logo"></a>')
    assert link.text == ""


def test_links_outside_the_article_are_ignored() -> None:
    links = links_in(
        '<a href="os.html">os</a>',
        outside='<div class="sphinxsidebar"><a href="sys.html">sys</a></div>',
    )
    assert [link.text for link in links] == ["os"]


def test_links_in_noise_inside_the_article_are_ignored() -> None:
    links = links_in(
        '<nav class="contents"><a href="sys.html">sys</a></nav><a href="os.html">os</a>'
    )
    assert [link.text for link in links] == ["os"]


def test_missing_content_area_raises() -> None:
    with pytest.raises(ContentNotFoundError):
        extract_links("<html><body><a href='os.html'>os</a></body></html>", PAGE, "python_docs")


# --- Saved fixtures ---


def test_python_docs_fixture_links() -> None:
    html = (FIXTURES / "python_docs" / "json.html").read_text(encoding="utf-8")
    links = extract_links(html, PAGE, "python_docs")
    targets = {link.target_url for link in links}
    assert len(links) > 0
    assert PAGE not in targets
    assert "https://docs.python.org/3/library/pickle.html" in targets


def test_mdn_fixture_links_skip_the_table_of_contents() -> None:
    page = (
        "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/map"
    )
    html = (FIXTURES / "mdn" / "array-map.html").read_text(encoding="utf-8")
    links = extract_links(html, page, "mdn")
    assert (
        Link(
            target_url="https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array",
            text="Array",
        )
        in links
    )
    assert "In this article" not in {link.text for link in links}


def test_devdocs_fixture_relative_links_stay_inside_the_doc() -> None:
    page = "https://devdocs.io/javascript/global_objects/array/map"
    html = (FIXTURES / "devdocs" / "js-array-map.html").read_text(encoding="utf-8")
    targets = {link.target_url for link in extract_links(html, page, "devdocs")}
    assert "https://devdocs.io/javascript/global_objects/array" in targets
