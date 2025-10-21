from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest
from x_make_common_x.json_contracts import validate_payload

from x_make_pypi_x import publish_flow
from x_make_pypi_x.json_contracts import ERROR_SCHEMA, OUTPUT_SCHEMA
from x_make_pypi_x.x_cls_make_pypi_x import main_json

pypi_module = importlib.import_module("x_make_pypi_x.x_cls_make_pypi_x")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_report_payload(repo_root: Path) -> dict[str, Any]:
    return {
        "run_id": "0123456789abcdef0123456789abcdef",
        "started_at": _iso(datetime(2025, 1, 1, 12, 0, 0)),
        "inputs": {
            "entry_count": 1,
            "manifest_entries": [
                {
                    "package": "demo_pkg",
                    "version": "1.2.3",
                    "pypi_name": "demo_pkg",
                    "ancillary": ["README.md"],
                    "options_kwargs": {"force_publish": True},
                }
            ],
            "repo_parent_root": str(repo_root),
            "token_env": "CUSTOM_ENV",
        },
        "execution": {"publisher_factory": "FakePublisher"},
        "result": {
            "status": "completed",
            "entries": [
                {
                    "package": "demo_pkg",
                    "distribution": "demo_pkg",
                    "version": "1.2.3",
                    "main_file": "x_cls_make_demo_pkg.py",
                    "ancillary_publish": ["README.md"],
                    "ancillary_manifest": ["README.md"],
                    "package_dir": f"{repo_root}/demo_pkg",
                    "safe_kwargs": {"force_publish": True},
                    "status": "published",
                }
            ],
            "published_versions": {"demo_pkg": "1.2.3"},
            "published_artifacts": {
                "demo_pkg": {"main": "x_cls_make_demo_pkg.py", "anc": ["README.md"]}
            },
        },
        "status": "completed",
        "completed_at": _iso(datetime(2025, 1, 1, 12, 5, 0)),
        "duration_seconds": 300.0,
        "tool": "x_make_pypi_x",
        "generated_at": _iso(datetime(2025, 1, 1, 12, 5, 0)),
        "errors": [],
    }


def _install_fake_publisher(monkeypatch: pytest.MonkeyPatch, module_name: str) -> None:
    fake_module = ModuleType(module_name)

    class FakePublisher:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.args = args
            self.kwargs = kwargs

        def publish(self, main_rel_path: str, ancillary_rel_paths: list[str]) -> bool:
            self.main_path = main_rel_path
            self.ancillary = ancillary_rel_paths
            return True

    fake_module.FakePublisher = FakePublisher  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, fake_module)


def _payload(template_repo_root: Path, publisher_identifier: str) -> dict[str, object]:
    return {
        "command": "x_make_pypi_x",
        "parameters": {
            "entries": [
                {
                    "package": "demo_pkg",
                    "version": "1.2.3",
                    "ancillary": ["README.md"],
                    "options": {
                        "author": "Author",
                        "dependencies": ["requests>=2"],
                        "ancillary_allowlist": ["docs/list.txt"],
                        "extra": {"force_publish": True},
                    },
                }
            ],
            "repo_parent_root": str(template_repo_root),
            "token_env": "CUSTOM_ENV",
            "context": {"dry_run": True},
            "publisher_factory": publisher_identifier,
        },
    }


def test_main_json_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module_name = "tests.fake_publisher"
    _install_fake_publisher(monkeypatch, module_name)

    calls: dict[str, Any] = {}

    def fake_publish(
        entries: Sequence[Any],
        *,
        cloner: object,
        ctx: object | None,
        repo_parent_root: str,
        publisher_factory: object,
        token_env: str,
    ) -> tuple[dict[str, str | None], dict[str, dict[str, object]], Path]:
        calls["entries"] = entries
        calls["ctx"] = ctx
        calls["repo_parent_root"] = repo_parent_root
        calls["publisher_factory"] = publisher_factory
        calls["token_env"] = token_env

        report_payload = _run_report_payload(tmp_path)
        report_path = tmp_path / "reports" / "x_make_pypi_x_run_test.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report_payload), encoding="utf-8")
        versions: dict[str, str | None] = {"demo_pkg": "1.2.3"}
        artifacts: dict[str, dict[str, object]] = {
            "demo_pkg": {"main": "x_cls_make_demo_pkg.py", "anc": ["README.md"]}
        }
        return versions, artifacts, report_path

    monkeypatch.setattr(pypi_module, "publish_manifest_entries", fake_publish)

    payload = _payload(tmp_path, f"{module_name}:FakePublisher")
    result = main_json(payload)

    validate_payload(result, OUTPUT_SCHEMA)

    entries = cast("Sequence[Any]", calls["entries"])
    assert entries and entries[0].package == "demo_pkg"
    ctx = calls["ctx"]
    assert isinstance(ctx, SimpleNamespace)
    assert getattr(ctx, "dry_run", False) is True
    assert calls["repo_parent_root"] == str(tmp_path)
    assert calls["token_env"] == "CUSTOM_ENV"
    publisher_factory_obj = calls.get("publisher_factory")
    assert callable(publisher_factory_obj)
    assert getattr(publisher_factory_obj, "__name__", "") == "FakePublisher"
    status_value = result.get("status")
    assert isinstance(status_value, str)
    assert status_value == "completed"


def test_main_json_publish_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def failing_publish(*_: Any, **__: Any) -> tuple[dict[str, str | None], dict[str, dict[str, object]], Path]:
        report_path = tmp_path / "reports" / "failed.json"
        exc = RuntimeError("publish boom")
        exc.run_report_path = report_path  # type: ignore[attr-defined]
        raise exc

    monkeypatch.setattr(pypi_module, "publish_manifest_entries", failing_publish)

    payload = _payload(tmp_path, "XClsMakePypiX")
    result = main_json(payload)

    validate_payload(result, ERROR_SCHEMA)

    details_obj = cast("Mapping[str, object] | None", result.get("details"))
    assert details_obj is not None
    assert "run_report_path" in details_obj


def test_main_json_rejects_invalid_payload() -> None:
    result = main_json({})
    validate_payload(result, ERROR_SCHEMA)
    status_value = result.get("status")
    assert isinstance(status_value, str)
    assert status_value == "failure"


def test_prime_twine_credentials_sets_username_and_password(monkeypatch: pytest.MonkeyPatch) -> None:
    token_value = "pypi-AgENdGVzdC10b2tlbg"
    monkeypatch.delenv("TWINE_API_TOKEN", raising=False)
    monkeypatch.delenv("TWINE_USERNAME", raising=False)
    monkeypatch.delenv("TWINE_PASSWORD", raising=False)
    custom_env = "CUSTOM_TOKEN_ENV"
    monkeypatch.setenv(custom_env, token_value)

    selected = publish_flow._prime_twine_credentials(custom_env)

    assert selected == custom_env
    assert os.environ["TWINE_API_TOKEN"] == token_value
    assert os.environ["TWINE_USERNAME"] == "__token__"
    assert os.environ["TWINE_PASSWORD"] == token_value


def test_prime_twine_credentials_preserves_existing_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWINE_API_TOKEN", "existing")
    monkeypatch.setenv("TWINE_USERNAME", "custom-user")
    monkeypatch.setenv("TWINE_PASSWORD", "custom-pass")

    selected = publish_flow._prime_twine_credentials("")

    assert selected == "TWINE_API_TOKEN"
    assert os.environ["TWINE_API_TOKEN"] == "existing"
    assert os.environ["TWINE_USERNAME"] == "__token__"
    assert os.environ["TWINE_PASSWORD"] == "existing"
