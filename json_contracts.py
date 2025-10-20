"""JSON contracts for x_make_pypi_x."""

from __future__ import annotations

_JSON_VALUE_SCHEMA: dict[str, object] = {
    "type": ["object", "array", "string", "number", "boolean", "null"],
}

_NON_EMPTY_STRING: dict[str, object] = {"type": "string", "minLength": 1}

_STRING_LIST_SCHEMA: dict[str, object] = {
    "type": "array",
    "items": _NON_EMPTY_STRING,
}

_DEPENDENCIES_SCHEMA: dict[str, object] = {
    "type": "array",
    "items": _NON_EMPTY_STRING,
}

_ALLOWLIST_SCHEMA: dict[str, object] = {
    "type": "array",
    "items": _NON_EMPTY_STRING,
}

_ENTRY_OPTIONS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "author": {
            "oneOf": [
                _NON_EMPTY_STRING,
                {"type": "null"},
            ]
        },
        "email": {
            "oneOf": [
                _NON_EMPTY_STRING,
                {"type": "null"},
            ]
        },
        "description": {
            "oneOf": [
                _NON_EMPTY_STRING,
                {"type": "null"},
            ]
        },
        "license_text": {
            "oneOf": [
                _NON_EMPTY_STRING,
                {"type": "null"},
            ]
        },
        "dependencies": _DEPENDENCIES_SCHEMA,
        "pypi_name": {
            "oneOf": [
                _NON_EMPTY_STRING,
                {"type": "null"},
            ]
        },
        "ancillary_allowlist": _ALLOWLIST_SCHEMA,
        "ancillary_list": _ALLOWLIST_SCHEMA,
        "extra": {
            "type": "object",
            "additionalProperties": _JSON_VALUE_SCHEMA,
        },
    },
    "additionalProperties": False,
}

_MANIFEST_ENTRY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "package": _NON_EMPTY_STRING,
        "version": _NON_EMPTY_STRING,
        "ancillary": {
            "type": "array",
            "items": _NON_EMPTY_STRING,
        },
        "options": _ENTRY_OPTIONS_SCHEMA,
    },
    "required": ["package", "version"],
    "additionalProperties": False,
}

_PARAMETERS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": _MANIFEST_ENTRY_SCHEMA,
            "minItems": 1,
        },
        "repo_parent_root": _NON_EMPTY_STRING,
        "token_env": _NON_EMPTY_STRING,
        "context": {
            "type": "object",
            "additionalProperties": _JSON_VALUE_SCHEMA,
        },
        "publisher_factory": _NON_EMPTY_STRING,
    },
    "required": ["entries", "repo_parent_root"],
    "additionalProperties": False,
}

INPUT_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_pypi_x input",
    "type": "object",
    "properties": {
        "command": {"const": "x_make_pypi_x"},
        "parameters": _PARAMETERS_SCHEMA,
    },
    "required": ["command", "parameters"],
    "additionalProperties": False,
}

_MANIFEST_ENTRY_REPORT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "package": _NON_EMPTY_STRING,
        "version": _NON_EMPTY_STRING,
        "pypi_name": _NON_EMPTY_STRING,
        "ancillary": {
            "type": "array",
            "items": _NON_EMPTY_STRING,
        },
        "options_kwargs": _JSON_VALUE_SCHEMA,
    },
    "required": ["package", "version", "pypi_name", "ancillary", "options_kwargs"],
    "additionalProperties": False,
}

_INPUTS_DETAIL_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "entry_count": {"type": "integer", "minimum": 0},
        "manifest_entries": {
            "type": "array",
            "items": _MANIFEST_ENTRY_REPORT_SCHEMA,
        },
        "repo_parent_root": _NON_EMPTY_STRING,
        "token_env": _NON_EMPTY_STRING,
    },
    "required": ["entry_count", "manifest_entries", "repo_parent_root"],
    "additionalProperties": False,
}

_EXECUTION_DETAIL_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "publisher_factory": _NON_EMPTY_STRING,
    },
    "required": ["publisher_factory"],
    "additionalProperties": False,
}

_ENTRY_RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "package": _NON_EMPTY_STRING,
        "distribution": _NON_EMPTY_STRING,
        "version": _NON_EMPTY_STRING,
        "main_file": _NON_EMPTY_STRING,
        "ancillary_publish": _STRING_LIST_SCHEMA,
        "ancillary_manifest": _STRING_LIST_SCHEMA,
        "package_dir": _NON_EMPTY_STRING,
        "safe_kwargs": {
            "type": "object",
            "additionalProperties": _JSON_VALUE_SCHEMA,
        },
        "status": {
            "type": "string",
            "enum": ["pending", "published", "skipped_existing", "error"],
        },
        "skip_reason": _NON_EMPTY_STRING,
        "error": _NON_EMPTY_STRING,
    },
    "required": [
        "package",
        "distribution",
        "version",
        "main_file",
        "ancillary_publish",
        "ancillary_manifest",
        "package_dir",
        "safe_kwargs",
        "status",
    ],
    "additionalProperties": False,
}

_PUBLISHED_ARTIFACT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "main": _NON_EMPTY_STRING,
        "anc": {
            "type": "array",
            "items": _NON_EMPTY_STRING,
        },
    },
    "required": ["main", "anc"],
    "additionalProperties": False,
}

_RESULT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["completed", "attention", "error", "running"],
        },
        "entries": {
            "type": "array",
            "items": _ENTRY_RESULT_SCHEMA,
        },
        "published_versions": {
            "type": "object",
            "additionalProperties": {
                "oneOf": [
                    _NON_EMPTY_STRING,
                    {"type": "null"},
                ]
            },
        },
        "published_artifacts": {
            "type": "object",
            "additionalProperties": _PUBLISHED_ARTIFACT_SCHEMA,
        },
    },
    "required": [
        "status",
        "entries",
        "published_versions",
        "published_artifacts",
    ],
    "additionalProperties": False,
}

ERROR_ENTRY_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "type": _NON_EMPTY_STRING,
        "message": _NON_EMPTY_STRING,
    },
    "required": ["type", "message"],
    "additionalProperties": True,
}

OUTPUT_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_pypi_x output",
    "type": "object",
    "properties": {
        "run_id": {
            "type": "string",
            "pattern": "^[a-f0-9]{32}$",
        },
        "started_at": {"type": "string", "format": "date-time"},
        "inputs": _INPUTS_DETAIL_SCHEMA,
        "execution": _EXECUTION_DETAIL_SCHEMA,
        "result": _RESULT_SCHEMA,
        "status": {
            "type": "string",
            "enum": ["completed", "attention", "error", "running"],
        },
        "errors": {
            "type": "array",
            "items": ERROR_ENTRY_SCHEMA,
        },
        "completed_at": {"type": "string", "format": "date-time"},
        "duration_seconds": {"type": "number", "minimum": 0},
        "tool": {"const": "x_make_pypi_x"},
        "generated_at": {"type": "string", "format": "date-time"},
    },
    "required": [
        "run_id",
        "started_at",
        "inputs",
        "execution",
        "result",
        "status",
        "completed_at",
        "duration_seconds",
        "tool",
        "generated_at",
    ],
    "additionalProperties": False,
}

ERROR_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "x_make_pypi_x error",
    "type": "object",
    "properties": {
        "status": {"const": "failure"},
        "message": _NON_EMPTY_STRING,
        "details": {
            "type": "object",
            "additionalProperties": _JSON_VALUE_SCHEMA,
        },
    },
    "required": ["status", "message"],
    "additionalProperties": True,
}

__all__ = ["ERROR_SCHEMA", "INPUT_SCHEMA", "OUTPUT_SCHEMA"]
