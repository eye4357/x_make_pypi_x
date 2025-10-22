from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from x_make_common_x.json_contracts import validate_payload, validate_schema

from x_make_pypi_x.json_contracts import (
    ERROR_SCHEMA,
    INPUT_SCHEMA,
    OUTPUT_SCHEMA,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "json_contracts"
REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


if TYPE_CHECKING:
    from collections.abc import Callable
else:
    pytest = cast("Any", pytest)

fixture = cast("Callable[..., Any]", pytest.fixture)


@fixture(scope="module")
def sample_input() -> dict[str, object]:
    with (FIXTURE_DIR / "input.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return cast("dict[str, object]", data)


@fixture(scope="module")
def sample_output() -> dict[str, object]:
    with (FIXTURE_DIR / "output.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return cast("dict[str, object]", data)


@fixture(scope="module")
def sample_error() -> dict[str, object]:
    with (FIXTURE_DIR / "error.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return cast("dict[str, object]", data)


def test_schemas_are_valid() -> None:
    for schema in (INPUT_SCHEMA, OUTPUT_SCHEMA, ERROR_SCHEMA):
        validate_schema(schema)


def test_sample_payloads_match_schema(
    sample_input: dict[str, object],
    sample_output: dict[str, object],
    sample_error: dict[str, object],
) -> None:
    validate_payload(sample_input, INPUT_SCHEMA)
    validate_payload(sample_output, OUTPUT_SCHEMA)
    validate_payload(sample_error, ERROR_SCHEMA)


def test_existing_reports_align_with_schema() -> None:
    if not REPORTS_DIR.exists():
        pytest.skip("no reports directory for pypi tool")
    report_files = sorted(REPORTS_DIR.glob("x_make_pypi_x_run_*.json"))
    if not report_files:
        pytest.skip("no pypi run reports to validate")
    for report_file in report_files:
        with report_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        validate_payload(payload, OUTPUT_SCHEMA)
