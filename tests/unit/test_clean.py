from pathlib import Path

import pytest

from docs_crawler.processing.blocks import (
    Block,
    CodeBlock,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    TableBlock,
)
from docs_crawler.processing.clean import CleanedPage, ContentNotFoundError, Site, clean_html

FIXTURES = Path(__file__).parent.parent / "fixtures" / "html"


def clean_mdn(body: str, head: str = "") -> CleanedPage:
    """Clean a small page whose article sits in MDN's content area."""
    return clean_html(
        f"<html><head>{head}</head><body><main id='content'>{body}</main></body></html>", "mdn"
    )


def texts(blocks: list[Block]) -> list[str]:
    return [block.text for block in blocks if isinstance(block, HeadingBlock | ParagraphBlock)]


def test_missing_content_area_raises_clear_error() -> None:
    with pytest.raises(ContentNotFoundError, match="main#content"):
        clean_html("<html><body><div>No article here</div></body></html>", "mdn")


def test_title_comes_from_first_h1() -> None:
    page = clean_mdn("<h1>Array.prototype.map()</h1><p>x</p>", head="<title>Map - MDN</title>")
    assert page.title == "Array.prototype.map()"


def test_title_falls_back_to_page_title() -> None:
    assert clean_mdn("<p>x</p>", head="<title>  Map -  MDN </title>").title == "Map - MDN"


def test_title_is_empty_when_page_has_none() -> None:
    assert clean_mdn("<p>x</p>").title == ""


def test_title_drops_permalink_sign() -> None:
    page = clean_mdn('<h1>json<a class="headerlink" href="#json">¶</a></h1>')
    assert page.title == "json"


def test_noise_text_never_reaches_blocks() -> None:
    page = clean_mdn(
        "<nav>Menu</nav><header>Top bar</header><p>Real text</p><script>track()</script>"
        "<style>p {}</style><aside>Sidebar</aside><button>Copy</button><footer>Legal</footer>"
        "<form><label>Search</label></form>"
    )
    assert texts(page.blocks) == ["Real text"]


def test_footnotes_are_kept() -> None:
    page = clean_mdn(
        '<aside class="footnote-list"><aside class="footnote"><p>[1] A note.</p></aside></aside>'
    )
    assert texts(page.blocks) == ["[1] A note."]


def test_blocks_keep_page_order() -> None:
    page = clean_mdn(
        "<h2>A</h2><p>para</p><ul><li>item</li></ul><pre>code</pre>"
        "<table><tr><td>cell</td></tr></table>"
    )
    assert [block.type for block in page.blocks] == [
        "heading",
        "paragraph",
        "list",
        "code",
        "table",
    ]


def test_heading_path_follows_heading_levels() -> None:
    page = clean_mdn("<h2>A</h2><p>in A</p><h3>B</h3><p>in B</p><h2>C</h2><p>in C</p>")
    paths = {
        block.text: block.heading_path for block in page.blocks if isinstance(block, ParagraphBlock)
    }
    assert paths == {"in A": ["A"], "in B": ["A", "B"], "in C": ["C"]}


def test_heading_path_of_a_heading_is_its_parents() -> None:
    page = clean_mdn("<h1>T</h1><h2>A</h2><h3>B</h3>")
    assert [block.heading_path for block in page.blocks] == [[], ["T"], ["T", "A"]]


def test_inline_tags_stay_in_one_paragraph() -> None:
    page = clean_mdn("<p>Call <code>map()</code> on <em>each</em> item.</p>")
    assert texts(page.blocks) == ["Call map() on each item."]


def test_loose_text_in_a_wrapper_becomes_a_paragraph() -> None:
    page = clean_mdn("<div>Loose <strong>text</strong><br>here<ul><li>x</li></ul></div>")
    assert texts(page.blocks) == ["Loose text here"]


def test_definition_term_becomes_a_paragraph() -> None:
    page = clean_mdn("<dl><dt><code>callbackFn</code></dt><dd>A function to run.</dd></dl>")
    assert texts(page.blocks) == ["callbackFn", "A function to run."]


def test_whitespace_is_collapsed_and_empty_blocks_dropped() -> None:
    page = clean_mdn("<h2> </h2><p>  many \n\n  spaces  </p><p>   </p><ul><li> </li></ul>")
    assert texts(page.blocks) == ["many spaces"]
    assert len(page.blocks) == 1


def test_list_items_keep_words_apart() -> None:
    page = clean_mdn("<ol><li><p>first</p><p>part</p></li><li>second</li></ol>")
    assert page.blocks == [ListBlock(heading_path=[], ordered=True, items=["first part", "second"])]


def test_code_keeps_indentation() -> None:
    page = clean_mdn("<pre>\ndef f():\n    return 1\n</pre>")
    assert page.blocks == [CodeBlock(heading_path=[], language=None, text="def f():\n    return 1")]


@pytest.mark.parametrize(
    ("html", "language"),
    [
        pytest.param('<pre class="language-js">x</pre>', "js", id="devdocs-language-class"),
        pytest.param('<pre class="brush: css notranslate">x</pre>', "css", id="mdn-brush-class"),
        pytest.param(
            '<div class="highlight-python3"><div class="highlight"><pre>x</pre></div></div>',
            "python3",
            id="python-docs-wrapper-class",
        ),
        pytest.param("<pre>x</pre>", None, id="no-language"),
        pytest.param('<pre class="brush:">x</pre>', None, id="brush-without-name"),
    ],
)
def test_code_language(html: str, language: str | None) -> None:
    [block] = clean_mdn(html).blocks
    assert isinstance(block, CodeBlock)
    assert block.language == language


def test_table_with_thead() -> None:
    page = clean_mdn(
        "<table><caption> JSON  types </caption>"
        "<thead><tr><th>JSON</th><th>Python</th></tr></thead>"
        "<tbody><tr><td>object</td><td>dict</td></tr><tr><td>array</td><td>list</td></tr></tbody>"
        "</table>"
    )
    assert page.blocks == [
        TableBlock(
            heading_path=[],
            caption="JSON types",
            headers=["JSON", "Python"],
            rows=[["object", "dict"], ["array", "list"]],
        )
    ]


def test_table_with_th_row_and_no_thead() -> None:
    [table] = clean_mdn(
        "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    ).blocks
    assert isinstance(table, TableBlock)
    assert (table.headers, table.rows) == (["A", "B"], [["1", "2"]])


def test_table_without_header_keeps_all_rows() -> None:
    [table] = clean_mdn(
        "<table><tr><td>1</td><td>2</td></tr><tr><td>3</td><td></td></tr></table>"
    ).blocks
    assert isinstance(table, TableBlock)
    assert (table.headers, table.rows) == ([], [["1", "2"], ["3", ""]])


def test_row_label_th_is_not_a_header() -> None:
    [table] = clean_mdn("<table><tr><th>Key</th><td>value</td></tr></table>").blocks
    assert isinstance(table, TableBlock)
    assert (table.headers, table.rows) == ([], [["Key", "value"]])


def test_nested_table_stays_inside_its_cell() -> None:
    [table] = clean_mdn(
        "<table><tr><th>outer</th></tr>"
        "<tr><td>cell <table><tr><td>inner</td></tr></table></td></tr></table>"
    ).blocks
    assert isinstance(table, TableBlock)
    assert table.rows == [["cell inner"]]


# --- Saved fixtures: real pages, cleaned the same way the crawler will clean them ---


def clean_fixture(site: Site, name: str) -> CleanedPage:
    return clean_html((FIXTURES / site / name).read_text(encoding="utf-8"), site)


def all_text(page: CleanedPage) -> str:
    """Every piece of text the page's blocks hold, joined into one string."""
    parts = [page.title]
    for block in page.blocks:
        if isinstance(block, HeadingBlock | ParagraphBlock | CodeBlock):
            parts.append(block.text)
        elif isinstance(block, ListBlock):
            parts.extend(block.items)
        else:
            parts.extend([block.caption or "", *block.headers, *(c for r in block.rows for c in r)])
    return " ".join(parts)


@pytest.mark.parametrize(
    ("site", "name", "title", "noise"),
    [
        pytest.param(
            "mdn",
            "array-map.html",
            "Array.prototype.map()",
            ["In this article", "Your blueprint for a better internet", "Skip to main content"],
            id="mdn-array-map",
        ),
        pytest.param(
            "mdn",
            "input-element.html",
            "<input> HTML input element",
            ["In this article", "Your blueprint for a better internet"],
            id="mdn-input-element",
        ),
        pytest.param(
            "python_docs",
            "json.html",
            "json — JSON encoder and decoder",
            ["Table of Contents", "Previous topic", "Report a bug", "¶"],
            id="python-json",
        ),
        pytest.param(
            "python_docs",
            "stdtypes.html",
            "Built-in Types",
            ["Table of Contents", "Previous topic", "¶"],
            id="python-stdtypes",
        ),
        pytest.param(
            "python_docs",
            "asyncio-task.html",
            "Coroutines and tasks",
            ["Table of Contents", "Previous topic", "¶"],
            id="python-asyncio-task",
        ),
        pytest.param(
            "devdocs",
            "python-json.html",
            "json — JSON encoder and decoder",
            ["DevDocs requires JavaScript", "Preferences"],
            id="devdocs-python-json",
        ),
        pytest.param(
            "devdocs",
            "js-array-map.html",
            "Array.prototype.map()",
            ["DevDocs requires JavaScript", "Preferences"],
            id="devdocs-js-array-map",
        ),
    ],
)
def test_fixture_has_title_and_no_page_chrome(
    site: Site, name: str, title: str, noise: list[str]
) -> None:
    page = clean_fixture(site, name)
    assert page.title == title
    text = all_text(page)
    for phrase in noise:
        assert phrase not in text
    block_types = {block.type for block in page.blocks}
    assert {"heading", "paragraph", "code"} <= block_types


def test_python_stdtypes_keeps_its_tables() -> None:
    tables = [b for b in clean_fixture("python_docs", "stdtypes.html").blocks if b.type == "table"]
    assert len(tables) >= 10
    assert all(table.headers for table in tables)


def test_python_json_table_has_headers_and_rows() -> None:
    page = clean_fixture("python_docs", "json.html")
    table = next(block for block in page.blocks if isinstance(block, TableBlock))
    assert table.headers == ["JSON", "Python"]
    assert table.rows[0] == ["object", "dict"]


def test_python_json_heading_paths_follow_the_page_outline() -> None:
    page = clean_fixture("python_docs", "json.html")
    paths = {tuple(block.heading_path) for block in page.blocks}
    assert ("json — JSON encoder and decoder", "Basic Usage") in paths


def test_python_json_keeps_footnotes() -> None:
    assert "errata for RFC 7159" in all_text(clean_fixture("python_docs", "json.html"))


def test_mdn_code_samples_are_javascript() -> None:
    page = clean_fixture("mdn", "array-map.html")
    languages = {block.language for block in page.blocks if isinstance(block, CodeBlock)}
    assert languages == {"js"}


def test_mdn_table_captions_are_kept() -> None:
    page = clean_fixture("mdn", "input-element.html")
    captions = [b.caption for b in page.blocks if isinstance(b, TableBlock) and b.caption]
    assert "Pseudo-classes relevant to the <input> element:" in captions


def test_cleaning_is_repeatable() -> None:
    assert clean_fixture("python_docs", "stdtypes.html") == clean_fixture(
        "python_docs", "stdtypes.html"
    )
