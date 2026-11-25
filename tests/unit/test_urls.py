
import pytest

from docs_crawler.crawler.urls import InvalidURLError, normalize_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        pytest.param(
            "HTTPS://Docs.Python.org/3/", "https://docs.python.org/3/", id="lowercase-scheme-host"
        ),
        pytest.param("https://site.org:443/a", "https://site.org/a", id="drop-https-port"),
        pytest.param("http://site.org:80/a", "http://site.org/a", id="drop-http-port"),
        pytest.param("https://site.org:8443/a", "https://site.org:8443/a", id="keep-custom-port"),
        pytest.param("https://site.org/a#section-2", "https://site.org/a", id="drop-fragment"),
        pytest.param("https://site.org/?b=2&a=1", "https://site.org/?a=1&b=2", id="sort-query"),
        pytest.param(
            "https://site.org/?id=5&utm_source=x&UTM_Medium=y&fbclid=f&gclid=g",
            "https://site.org/?id=5",
            id="strip-tracking-params",
        ),
        pytest.param("https://site.org/?q=", "https://site.org/?q=", id="keep-blank-values"),
        pytest.param(
            "https://site.org/3//library///x", "https://site.org/3/library/x", id="dup-slashes"
        ),
        pytest.param(
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
            id="keep-path-case",
        ),
        pytest.param("https://site.org", "https://site.org/", id="empty-path-becomes-slash"),
        pytest.param("https://site.org/docs/", "https://site.org/docs/", id="keep-trailing-slash"),
        pytest.param("  https://site.org/a  ", "https://site.org/a", id="strip-whitespace"),
        pytest.param("https://user:pw@site.org/a", "https://site.org/a", id="drop-credentials"),
        pytest.param("http://[::1]:8000/a", "http://[::1]:8000/a", id="ipv6-host"),
    ],
)
def test_normalize_absolute_urls(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


@pytest.mark.parametrize(
    ("url", "base", "expected"),
    [
        pytest.param(
            "../tutorial/",
            "https://docs.python.org/3/library/asyncio.html",
            "https://docs.python.org/3/tutorial/",
            id="parent-dir",
        ),
        pytest.param(
            "asyncio-task.html#coroutines",
            "https://docs.python.org/3/library/asyncio.html",
            "https://docs.python.org/3/library/asyncio-task.html",
            id="same-dir-with-fragment",
        ),
        pytest.param(
            "/en-US/docs/Web/HTML",
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
            "https://developer.mozilla.org/en-US/docs/Web/HTML",
            id="root-relative",
        ),
        pytest.param(
            "//cdn.site.org/x", "https://site.org/a", "https://cdn.site.org/x", id="scheme-relative"
        ),
        pytest.param(
            "https://other.org/b", "https://site.org/a", "https://other.org/b", id="absolute-wins"
        ),
    ],
)
def test_resolves_relative_links_against_base(url: str, base: str, expected: str) -> None:
    assert normalize_url(url, base=base) == expected


@pytest.mark.parametrize(
    ("url", "base"),
    [
        pytest.param("mailto:docs@site.org", "https://site.org/", id="mailto"),
        pytest.param("javascript:void(0)", "https://site.org/", id="javascript"),
        pytest.param("ftp://site.org/file", None, id="ftp"),
        pytest.param("/relative/without/base", None, id="relative-without-base"),
        pytest.param("https:///no-host", None, id="missing-host"),
        pytest.param("https://site.org:99999/a", None, id="invalid-port"),
    ],
)
def test_rejects_links_that_cannot_be_crawled(url: str, base: str | None) -> None:
    with pytest.raises(InvalidURLError):
        normalize_url(url, base=base)


def test_normalized_url_is_stable() -> None:
    once = normalize_url("HTTP://Site.org:80//a//b?z=1&a=2&utm_id=3#top")
    assert normalize_url(once) == once