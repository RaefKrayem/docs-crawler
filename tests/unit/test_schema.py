from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from docs_crawler.processing.blocks import ParagraphBlock
from docs_crawler.processing.clean import CleanedPage, clean_html
from docs_crawler.processing.schema import (
    CleanDocument,
    Rejection,
    build_document,
    document_id,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "html"
URL = "https://docs.python.org/3/library/json.html"
HASH = "0" * 63 + "a"
CRAWLED_AT = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)
PAGE = CleanedPage(title="json", blocks=[ParagraphBlock(heading_path=["json"], text="Encode.")])


def build(**changes: Any) -> CleanDocument | Rejection:
    """build_document with valid defaults; `changes` replaces some of them."""
    arguments: dict[str, Any] = {
        "url": URL,
        "site": "python_docs",
        "html": "<html><head><title>json — Python 3.15.2 documentation</title></head></html>",
        "page": PAGE,
        "content_hash": HASH,
        "crawled_at": CRAWLED_AT,
        "version": 1,
    }
    return build_document(**{**arguments, **changes})


def test_valid_fixture_becomes_a_document_with_every_field() -> None:
    html = (FIXTURES / "python_docs" / "json.html").read_text(encoding="utf-8")
    document = build(html=html, page=clean_html(html, "python_docs"))
    assert isinstance(document, CleanDocument)
    assert document.id == document_id(URL, 1)
    assert (document.url, document.site, document.version) == (URL, "python_docs", 1)
    assert document.title == "json — JSON encoder and decoder"
    assert len(document.blocks) > 100
    assert (document.content_hash, document.crawled_at) == (HASH, CRAWLED_AT)
    assert document.site_fields == {"module": "json", "docs_version": "3.15.2"}


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        pytest.param(
            {"page": CleanedPage(title="", blocks=PAGE.blocks)}, "title", id="empty-title"
        ),
        pytest.param({"page": CleanedPage(title="json", blocks=[])}, "blocks", id="no-blocks"),
        pytest.param({"content_hash": "abc"}, "content_hash", id="short-hash"),
        pytest.param({"content_hash": "A" * 64}, "content_hash", id="uppercase-hash"),
        pytest.param({"crawled_at": datetime(2026, 11, 28, 12, 0)}, "crawled_at", id="naive-time"),
        pytest.param({"version": 0}, "version", id="version-0"),
        pytest.param({"url": ""}, "url", id="empty-url"),
    ],
)
def test_invalid_input_becomes_a_rejection_naming_the_field(
    changes: dict[str, Any], field: str
) -> None:
    rejection = build(**changes)
    assert isinstance(rejection, Rejection)
    assert rejection.url == changes.get("url", URL)
    assert rejection.reason.startswith(f"{field}: ")


def test_rejection_lists_every_problem() -> None:
    rejection = build(page=CleanedPage(title="", blocks=[]), content_hash="x")
    assert isinstance(rejection, Rejection)
    assert [part.split(":")[0] for part in rejection.reason.split("; ")] == [
        "title",
        "blocks",
        "content_hash",
    ]


def test_same_url_and_version_give_the_same_id() -> None:
    first, second = build(), build()
    assert isinstance(first, CleanDocument)
    assert isinstance(second, CleanDocument)
    assert first.id == second.id == document_id(URL, 1)


@pytest.mark.parametrize(
    ("url", "version"),
    [
        pytest.param(URL, 2, id="other-version"),
        pytest.param("https://docs.python.org/3/library/os.html", 1, id="other-url"),
    ],
)
def test_other_url_or_version_gives_another_id(url: str, version: int) -> None:
    assert document_id(url, version) != document_id(URL, 1)


def test_document_rejects_an_id_that_does_not_match() -> None:
    with pytest.raises(ValidationError, match="id must be document_id"):
        CleanDocument(
            id=uuid4(),
            url=URL,
            site="python_docs",
            title="json",
            blocks=PAGE.blocks,
            content_hash=HASH,
            crawled_at=CRAWLED_AT,
            version=1,
            site_fields={},
        )


def test_document_rejects_unknown_fields_and_sites() -> None:
    valid = build()
    assert isinstance(valid, CleanDocument)
    data = valid.model_dump()
    with pytest.raises(ValidationError):
        CleanDocument.model_validate({**data, "author": "someone"})
    with pytest.raises(ValidationError):
        CleanDocument.model_validate({**data, "site": "w3schools"})


def test_document_survives_json_round_trip() -> None:
    document = build()
    assert isinstance(document, CleanDocument)
    assert CleanDocument.model_validate_json(document.model_dump_json()) == document
