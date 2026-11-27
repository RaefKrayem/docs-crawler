import pytest
from pydantic import TypeAdapter, ValidationError

from docs_crawler.processing.blocks import (
    BaseBlock,
    Block,
    CodeBlock,
    HeadingBlock,
    ListBlock,
    ParagraphBlock,
    TableBlock,
)

BLOCK: TypeAdapter[Block] = TypeAdapter(Block)
PATH = ["json — JSON encoder and decoder", "Basic Usage"]


@pytest.mark.parametrize("level", [1, 6])
def test_heading_accepts_levels_1_to_6(level: int) -> None:
    assert HeadingBlock(heading_path=[], level=level, text="Basic Usage").level == level


@pytest.mark.parametrize("level", [0, 7])
def test_heading_rejects_levels_outside_1_to_6(level: int) -> None:
    with pytest.raises(ValidationError):
        HeadingBlock.model_validate({"heading_path": [], "level": level, "text": "Basic Usage"})


@pytest.mark.parametrize(
    ("model", "data"),
    [
        pytest.param(HeadingBlock, {"level": 2, "text": ""}, id="heading-text"),
        pytest.param(ParagraphBlock, {"text": ""}, id="paragraph-text"),
        pytest.param(ListBlock, {"ordered": False, "items": []}, id="list-without-items"),
        pytest.param(ListBlock, {"ordered": False, "items": ["a", ""]}, id="list-empty-item"),
        pytest.param(CodeBlock, {"language": None, "text": ""}, id="code-text"),
        pytest.param(CodeBlock, {"language": "", "text": "x = 1"}, id="code-empty-language"),
        pytest.param(
            TableBlock, {"caption": "", "headers": [], "rows": [["a"]]}, id="table-empty-caption"
        ),
        pytest.param(TableBlock, {"caption": None, "headers": [], "rows": []}, id="table-no-rows"),
    ],
)
def test_rejects_empty_content(model: type[BaseBlock], data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({"heading_path": [], **data})


def test_table_allows_missing_headers_and_empty_cells() -> None:
    table = TableBlock(heading_path=[], caption=None, headers=[], rows=[["object", ""]])
    assert table.rows == [["object", ""]]


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ParagraphBlock.model_validate({"heading_path": [], "text": "x", "colour": "red"})


@pytest.mark.parametrize(
    "block",
    [
        pytest.param(HeadingBlock(heading_path=[], level=1, text="json"), id="heading"),
        pytest.param(ParagraphBlock(heading_path=PATH, text="Serialize obj."), id="paragraph"),
        pytest.param(ListBlock(heading_path=PATH, ordered=True, items=["a", "b"]), id="list"),
        pytest.param(
            CodeBlock(heading_path=PATH, language="python", text="import json"), id="code"
        ),
        pytest.param(
            TableBlock(
                heading_path=PATH,
                caption=None,
                headers=["JSON", "Python"],
                rows=[["object", "dict"]],
            ),
            id="table",
        ),
    ],
)
def test_block_survives_json_round_trip(block: Block) -> None:
    assert BLOCK.validate_json(BLOCK.dump_json(block)) == block


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({"type": "heading", "level": 2, "text": "x"}, HeadingBlock, id="heading"),
        pytest.param({"type": "paragraph", "text": "x"}, ParagraphBlock, id="paragraph"),
        pytest.param({"type": "list", "ordered": False, "items": ["x"]}, ListBlock, id="list"),
        pytest.param({"type": "code", "language": None, "text": "x"}, CodeBlock, id="code"),
        pytest.param(
            {"type": "table", "caption": None, "headers": [], "rows": [["x"]]},
            TableBlock,
            id="table",
        ),
    ],
)
def test_type_field_picks_the_right_class(
    data: dict[str, object], expected: type[BaseBlock]
) -> None:
    assert type(BLOCK.validate_python({"heading_path": [], **data})) is expected


def test_type_label_is_filled_in_automatically() -> None:
    assert ParagraphBlock(heading_path=[], text="x").type == "paragraph"


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"type": "video", "text": "x"}, id="unknown-type"),
        pytest.param({"text": "x"}, id="missing-type"),
    ],
)
def test_rejects_unknown_or_missing_type(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BLOCK.validate_python({"heading_path": [], **data})
