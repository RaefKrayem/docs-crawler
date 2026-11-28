from pathlib import Path
from typing import get_args

import pytest

from docs_crawler.processing.clean import Site
from docs_crawler.processing.extractors import EXTRACTORS, devdocs, mdn, python_docs

FIXTURES = Path(__file__).parent.parent / "fixtures" / "html"
MDN = "https://developer.mozilla.org/en-US/docs/"


def fixture(site: str, name: str) -> str:
    return (FIXTURES / site / name).read_text(encoding="utf-8")


def test_every_site_has_an_extractor() -> None:
    assert set(EXTRACTORS) == set(get_args(Site))


# --- MDN ---


def test_mdn_fixture_fields() -> None:
    fields = mdn.extract_site_fields(
        fixture("mdn", "array-map.html"), MDN + "Web/JavaScript/Reference/Global_Objects/Array/map"
    )
    assert fields == {
        "section": "Web/JavaScript/Reference",
        "last_modified": "2026-10-26T04:56:01.000Z",
    }


@pytest.mark.parametrize(
    ("path", "section"),
    [
        pytest.param("Web/HTML/Reference/Elements/input", "Web/HTML/Reference", id="deep-page"),
        pytest.param("Glossary/User_agent", "Glossary", id="shallow-page"),
    ],
)
def test_mdn_section_comes_from_the_url(path: str, section: str) -> None:
    assert mdn.extract_site_fields("<p>x</p>", MDN + path) == {"section": section}


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(MDN + "Web", id="top-level-page"),
        pytest.param("https://developer.mozilla.org/en-US/", id="not-a-docs-page"),
    ],
)
def test_mdn_leaves_out_fields_the_page_does_not_have(url: str) -> None:
    assert mdn.extract_site_fields("<p>no footer</p>", url) == {}


# --- Python docs ---


def test_python_docs_module_page() -> None:
    fields = python_docs.extract_site_fields(fixture("python_docs", "json.html"), "")
    assert fields == {"module": "json", "docs_version": "3.15.2"}


def test_python_docs_page_without_module() -> None:
    fields = python_docs.extract_site_fields(fixture("python_docs", "stdtypes.html"), "")
    assert fields == {"docs_version": "3.15.2"}


def test_python_docs_page_without_title() -> None:
    assert python_docs.extract_site_fields("<p>x</p>", "") == {}


# --- DevDocs ---


@pytest.mark.parametrize(
    ("path", "fields"),
    [
        pytest.param(
            "python~3.15/library/json",
            {"doc_slug": "python", "doc_version": "3.15"},
            id="with-version",
        ),
        pytest.param(
            "javascript/global_objects/array/map", {"doc_slug": "javascript"}, id="no-version"
        ),
        pytest.param("", {}, id="home-page"),
    ],
)
def test_devdocs_fields_come_from_the_url(path: str, fields: dict[str, str]) -> None:
    html = fixture("devdocs", "python-json.html")
    assert devdocs.extract_site_fields(html, "https://devdocs.io/" + path) == fields
