"""The schema every cleaned document must pass before it is saved."""

from datetime import datetime
from typing import Annotated, Self
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from docs_crawler.processing.blocks import Block, NonEmptyStr
from docs_crawler.processing.clean import CleanedPage, Site
from docs_crawler.processing.extractors import extract_site_fields

# SHA-256 written as 64 lowercase hex characters
ContentHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


def document_id(url: str, version: int) -> UUID:
    """Return the id of one version of a page; the same url + version always give the same id.

    A job that runs twice (after a retry or a crashed worker) therefore builds a document
    with the same id, so the database can ignore the second copy instead of storing it.
    """
    return uuid5(NAMESPACE_URL, f"{url}#v{version}")


class CleanDocument(BaseModel):
    """One version of one page, cleaned and ready to store.

    `crawled_at` must carry a timezone, so times from different workers compare correctly.
    `site_fields` holds the extra fields a site's extractor finds (empty if none).
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    url: NonEmptyStr
    site: Site
    title: NonEmptyStr
    blocks: list[Block] = Field(min_length=1)
    content_hash: ContentHash
    crawled_at: AwareDatetime
    version: int = Field(ge=1)
    site_fields: dict[str, str]

    @model_validator(mode="after")
    def _id_matches_url_and_version(self) -> Self:
        expected = document_id(self.url, self.version)
        if self.id != expected:
            raise ValueError(f"id must be document_id(url, version) = {expected}")
        return self


class Rejection(BaseModel):
    """A page that failed validation, with a reason a person can read in the logs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    reason: str


def build_document(
    *,
    url: str,
    site: Site,
    html: str,
    page: CleanedPage,
    content_hash: str,
    crawled_at: datetime,
    version: int,
) -> CleanDocument | Rejection:
    """Combine a cleaned page with its metadata and site fields into a validated document.

    `url` must already be canonical (see `normalize_url`), because it is part of the id.
    Invalid input never raises: the caller gets a Rejection to log and store instead.
    """
    try:
        return CleanDocument(
            id=document_id(url, version),
            url=url,
            site=site,
            title=page.title,
            blocks=page.blocks,
            content_hash=content_hash,
            crawled_at=crawled_at,
            version=version,
            site_fields=extract_site_fields(site, html, url),
        )
    except ValidationError as error:
        return Rejection(url=url, reason=_readable_reason(error))


def _readable_reason(error: ValidationError) -> str:
    """Turn Pydantic's errors into one line, e.g. "title: String should have at least 1 …"."""
    problems = []
    for problem in error.errors():
        field = ".".join(str(part) for part in problem["loc"]) or "document"
        problems.append(f"{field}: {problem['msg']}")
    return "; ".join(problems)
