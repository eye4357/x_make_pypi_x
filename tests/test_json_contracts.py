from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar, cast

import pytest
from x_make_common_x.json_contracts import validate_payload, validate_schema

from x_make_pypi_x.json_contracts import (
    ERROR_SCHEMA,
    INPUT_SCHEMA,
    OUTPUT_SCHEMA,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "json_contracts"
REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"

FixtureFunc = TypeVar("FixtureFunc", bound=Callable[[], dict[str, object]])


def _module_fixture(func: FixtureFunc) -> FixtureFunc:
    decorator: Callable[[FixtureFunc], object] = pytest.fixture(scope="module")
    return cast("FixtureFunc", decorator(func))


def _load_fixture(name: str) -> dict[str, object]:
    path = FIXTURE_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        message = f"Fixture payload must be an object: {name}"
        raise TypeError(message)
    return cast("dict[str, object]", payload)


@_module_fixture
def sample_input() -> dict[str, object]:
    return _load_fixture("input")


@_module_fixture
def sample_output() -> dict[str, object]:
    return _load_fixture("output")


@_module_fixture
def sample_error() -> dict[str, object]:
    return _load_fixture("error")


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
        if not isinstance(payload, dict):
            message = f"Report payload must be an object: {report_file}"
            raise TypeError(message)
        typed_payload = cast("dict[str, object]", payload)
        validate_payload(typed_payload, OUTPUT_SCHEMA)
