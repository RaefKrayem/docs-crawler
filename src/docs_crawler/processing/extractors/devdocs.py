"""DevDocs site fields: which documentation set a page belongs to, and its version."""

from urllib.parse import urlsplit


def extract_site_fields(html: str, url: str) -> dict[str, str]:
    """Return `doc_slug` and, when the URL has one, `doc_version`.

    DevDocs puts both in the first path segment: /python~3.15/library/json gives
    python + 3.15, while /javascript/global_objects/array/map has no version.
    `html` is unused; it is accepted so every site's extractor has the same signature.
    """
    first_segment = next((part for part in urlsplit(url).path.split("/") if part), "")
    slug, _, version = first_segment.partition("~")
    fields: dict[str, str] = {}
    if slug:
        fields["doc_slug"] = slug
    if version:
        fields["doc_version"] = version
    return fields
