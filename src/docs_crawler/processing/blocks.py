"""Content blocks: the ordered pieces a cleaned page is made of.

Each block keeps `heading_path`, the headings it sits under (for example
["json — JSON encoder and decoder", "Basic Usage"]), so a block still makes sense on its
own when it is searched or embedded later.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]


class BaseBlock(BaseModel):
    """Fields shared by every content block."""

    model_config = ConfigDict(extra="forbid")

    heading_path: list[str]


class HeadingBlock(BaseBlock):
    """An `<h1>`-`<h6>` heading."""

    type: Literal["heading"] = "heading"
    level: int = Field(ge=1, le=6)
    text: NonEmptyStr


class ParagraphBlock(BaseBlock):
    """A `<p>` paragraph."""

    type: Literal["paragraph"] = "paragraph"
    text: NonEmptyStr


class ListBlock(BaseBlock):
    """A `<ul>` (ordered=False) or `<ol>` (ordered=True) list."""

    type: Literal["list"] = "list"
    ordered: bool
    items: list[NonEmptyStr] = Field(min_length=1)


class CodeBlock(BaseBlock):
    """A `<pre>` code sample; `language` is None when the page does not say."""

    type: Literal["code"] = "code"
    language: NonEmptyStr | None
    text: NonEmptyStr


class TableBlock(BaseBlock):
    """A `<table>` kept as rows and columns.

    `headers` is empty when the table has no header row. Cells may be empty strings,
    because real tables have empty cells.
    """

    type: Literal["table"] = "table"
    caption: NonEmptyStr | None
    headers: list[str]
    rows: list[list[str]] = Field(min_length=1)


# Any one block. Pydantic reads the `type` field to pick the right class when loading JSON.
Block = Annotated[
    HeadingBlock | ParagraphBlock | ListBlock | CodeBlock | TableBlock,
    Field(discriminator="type"),
]
