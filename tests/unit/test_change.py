from datetime import UTC, datetime
from pathlib import Path

import pytest

from docs_crawler.processing.blocks import Block, ParagraphBlock, TableBlock
from docs_crawler.processing.change import ChangeDecision, conditional_headers, decide
from docs_crawler.processing.clean import clean_html
from docs_crawler.processing.hashing import content_hash
from docs_crawler.processing.schema import CleanDocument, document_id

FIXTURES = Path(__file__).parent.parent / "fixtures" / "html"
OLD, NEW = "a" * 64, "b" * 64


def paragraph(text: str, path: list[str] | None = None) -> ParagraphBlock:
    return ParagraphBlock(heading_path=path or ["json"], text=text)


def hash_of_page(html: str) -> str:
    page = clean_html(f'<div class="body" role="main">{html}</div>', "python_docs")
    return content_hash(page.title, page.blocks)


# --- content_hash ---


def test_hash_is_accepted_by_the_document_schema() -> None:
    blocks: list[Block] = [paragraph("Encode.")]
    url = "https://docs.python.org/3/library/json.html"
    document = CleanDocument(
        id=document_id(url, 1),
        url=url,
        site="python_docs",
        title="json",
        blocks=blocks,
        content_hash=content_hash("json", blocks),
        crawled_at=datetime(2026, 11, 28, tzinfo=UTC),
        version=1,
        site_fields={},
    )
    assert len(document.content_hash) == 64


def test_same_content_gives_the_same_hash() -> None:
    blocks: list[Block] = [paragraph("a"), paragraph("b")]
    assert content_hash("json", blocks) == content_hash("json", [paragraph("a"), paragraph("b")])


def test_extra_whitespace_and_scripts_do_not_change_the_hash() -> None:
    plain = hash_of_page("<h1>json</h1><p>Encode objects.</p>")
    noisy = hash_of_page(
        "\n  <h1>  json </h1>\n\n<p>Encode \n   objects.</p><script>track()</script><nav>Menu</nav>"
    )
    assert plain == noisy


@pytest.mark.parametrize(
    ("title", "blocks"),
    [
        pytest.param("json", [paragraph("a"), paragraph("changed")], id="changed-paragraph"),
        pytest.param("json", [paragraph("b"), paragraph("a")], id="reordered-blocks"),
        pytest.param("JSON", [paragraph("a"), paragraph("b")], id="changed-title"),
        pytest.param("json", [paragraph("a", ["other"]), paragraph("b")], id="moved-section"),
        pytest.param("json", [paragraph("a")], id="removed-block"),
    ],
)
def test_any_content_change_gives_another_hash(title: str, blocks: list[Block]) -> None:
    assert content_hash(title, blocks) != content_hash("json", [paragraph("a"), paragraph("b")])


def test_table_cell_change_gives_another_hash() -> None:
    def table(cell: str) -> list[Block]:
        return [TableBlock(heading_path=[], caption=None, headers=["JSON"], rows=[[cell]])]

    assert content_hash("t", table("object")) != content_hash("t", table("array"))


def test_saved_fixture_hashes_the_same_every_time() -> None:
    html = (FIXTURES / "python_docs" / "stdtypes.html").read_text(encoding="utf-8")
    first, second = clean_html(html, "python_docs"), clean_html(html, "python_docs")
    assert content_hash(first.title, first.blocks) == content_hash(second.title, second.blocks)


# --- conditional_headers ---


@pytest.mark.parametrize(
    ("etag", "last_modified", "headers"),
    [
        pytest.param(None, None, {}, id="nothing-stored"),
        pytest.param('"abc123"', None, {"If-None-Match": '"abc123"'}, id="etag-only"),
        pytest.param(
            None,
            "Wed, 25 Nov 2026 20:00:00 GMT",
            {"If-Modified-Since": "Wed, 25 Nov 2026 20:00:00 GMT"},
            id="last-modified-only",
        ),
        pytest.param(
            'W/"x"',
            "Wed, 25 Nov 2026 20:00:00 GMT",
            {"If-None-Match": 'W/"x"', "If-Modified-Since": "Wed, 25 Nov 2026 20:00:00 GMT"},
            id="both",
        ),
        pytest.param("  ", "", {}, id="blank-values"),
    ],
)
def test_conditional_headers(
    etag: str | None, last_modified: str | None, headers: dict[str, str]
) -> None:
    assert conditional_headers(etag, last_modified) == headers


# --- decide ---


@pytest.mark.parametrize(
    ("status", "new_hash", "previous_hash", "decision"),
    [
        pytest.param(200, NEW, None, ChangeDecision.NEW, id="first-crawl"),
        pytest.param(200, OLD, OLD, ChangeDecision.UNCHANGED, id="same-hash"),
        pytest.param(200, NEW, OLD, ChangeDecision.CHANGED, id="different-hash"),
        pytest.param(304, None, OLD, ChangeDecision.NOT_MODIFIED, id="304"),
        pytest.param(404, None, OLD, ChangeDecision.REMOVED, id="404"),
        pytest.param(410, None, OLD, ChangeDecision.REMOVED, id="410"),
        pytest.param(404, None, None, ChangeDecision.REMOVED, id="404-never-stored"),
    ],
)
def test_decide(
    status: int, new_hash: str | None, previous_hash: str | None, decision: ChangeDecision
) -> None:
    assert decide(status, new_hash, previous_hash) is decision


@pytest.mark.parametrize(
    ("status", "new_hash", "previous_hash"),
    [
        pytest.param(503, None, OLD, id="server-error"),
        pytest.param(429, None, OLD, id="rate-limited"),
        pytest.param(301, None, OLD, id="redirect"),
        pytest.param(304, None, None, id="304-without-stored-version"),
        pytest.param(200, None, OLD, id="200-without-hash"),
    ],
)
def test_decide_rejects_answers_that_are_not_content(
    status: int, new_hash: str | None, previous_hash: str | None
) -> None:
    with pytest.raises(ValueError):
        decide(status, new_hash, previous_hash)
