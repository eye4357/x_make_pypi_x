# pyright: reportMissingImports=false
from __future__ import annotations

import os
import subprocess
import time
import uuid
from collections.abc import Mapping, Sequence
from contextlib import chdir, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from x_make_common_x import (
    HttpClient,
    HttpError,
    isoformat_timestamp,
    log_error,
    log_info,
    write_run_report,
)
from x_make_common_x.telemetry import emit_event, make_event

PACKAGE_ROOT = Path(__file__).resolve().parent


JSONValue = str | int | float | bool | None | dict[str, "JSONValue"] | list["JSONValue"]


def _json_ready(value: object) -> JSONValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        typed_mapping = cast("Mapping[object, object]", value)
        return {str(key): _json_ready(val) for key, val in typed_mapping.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        typed_sequence = cast("Sequence[object]", value)
        return [_json_ready(entry) for entry in typed_sequence]
    return str(value)


if TYPE_CHECKING:
    from x_0_make_all_x.manifest import ManifestEntry, ManifestOptions


class PublisherProtocol(Protocol):
    def publish(self, main_rel_path: str, ancillary_rel_paths: list[str]) -> bool: ...


class PublisherFactory(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> PublisherProtocol: ...


TEST_PYPI_TOKEN_ENV = "TEST_PYPI_TOKEN"  # noqa: S105 - environment variable name


@dataclass(frozen=True)
class PublishContext:
    name: str
    version: str
    main_path: Path
    pkg_path: Path
    ancillary_rel: list[str]
    safe_kwargs: dict[str, object]


def _info(*parts: object) -> None:
    log_info(*parts)


def _error(*parts: object) -> None:
    log_error(*parts)


def _stringify_maybe(value: object) -> str | None:
    if isinstance(value, bytes):
        decoded = value.decode(errors="ignore").strip()
        return decoded or None
    text = str(value).strip()
    return text or None


def _iter_exception_args(raw_args: object) -> list[str]:
    def _collect(items: Sequence[object]) -> list[str]:
        results: list[str] = []
        for item in items:
            rendered = _stringify_maybe(item)
            if rendered:
                results.append(rendered)
        return results

    if isinstance(raw_args, tuple):
        return _collect(cast("tuple[object, ...]", raw_args))
    if isinstance(raw_args, list):
        return _collect(cast("list[object]", raw_args))
    single = _stringify_maybe(raw_args)
    return [single] if single is not None else []


def _iter_exception_streams(exc: BaseException) -> list[str]:
    results: list[str] = []
    for attr in ("stdout", "stderr", "output"):
        attr_value: object | None = getattr(exc, attr, None)
        if attr_value is None:
            continue
        rendered = _stringify_maybe(attr_value)
        if rendered:
            results.append(rendered)
    return results


def _exception_summary(exc: BaseException) -> str:
    parts: list[str] = []
    primary = _stringify_maybe(exc)
    if primary:
        parts.append(primary)
    parts.extend(_iter_exception_args(getattr(exc, "args", ())))
    parts.extend(_iter_exception_streams(exc))
    return " ".join(parts).strip()


def options_to_kwargs(options: ManifestOptions) -> dict[str, object]:
    base_pairs = (
        ("author", options.author),
        ("email", options.email),
        ("description", options.description),
        ("license_text", options.license_text),
        ("pypi_name", options.pypi_name),
    )
    kwargs: dict[str, object] = {
        key: value for key, value in base_pairs if value is not None
    }
    kwargs["dependencies"] = list(options.dependencies or [])
    if options.ancillary_allowlist:
        kwargs["ancillary_allowlist"] = list(options.ancillary_allowlist)
    if options.ancillary_list:
        kwargs["ancillary_list"] = list(options.ancillary_list)
    if options.extra:
        kwargs.update(options.extra)
    return kwargs


def _normalize_allowlist_specs(
    safe_kwargs: Mapping[str, object],
) -> list[str]:
    allow_spec = safe_kwargs.get("ancillary_allowlist") or safe_kwargs.get(
        "ancillary_list"
    )
    if allow_spec is None:
        return []
    if isinstance(allow_spec, str):
        return [allow_spec]
    if isinstance(allow_spec, list):
        normalized: list[str] = []
        for item in cast("list[object | None]", allow_spec):
            if item is None:
                continue
            normalized.append(item if isinstance(item, str) else str(item))
        return normalized
    return []


def _to_posix_rel(rel: str) -> str:
    rel_str = rel.strip().lstrip("/\\")
    return rel_str.replace("\\", "/")


def _safe_rel_from_abs(abs_path: str, base_dir: str) -> str | None:
    abs_obj = Path(abs_path)
    base_obj = Path(base_dir)
    try:
        abs_resolved = abs_obj.resolve()
        base_resolved = base_obj.resolve()
    except OSError:
        return None
    if not abs_resolved.is_file():
        return None
    try:
        rel = abs_resolved.relative_to(base_resolved)
    except ValueError:
        return None
    return rel.as_posix()


def _load_ancillary_allowlist(list_file: str, pkg_dir: str) -> list[str]:
    out: list[str] = []
    pkg_path = Path(pkg_dir).resolve()
    list_path = Path(list_file)
    with suppress(OSError):
        list_path = list_path.resolve()
    if not list_path.is_file():
        _info(f"Ancillary allowlist not found: {list_path}")
        return out
    try:
        lines = list_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _error(f"Failed to read ancillary allowlist {list_path}: {exc}")
        return out

    seen: set[str] = set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            line = line[1:].strip()
        entry_fragment = Path(line)
        candidate = (
            entry_fragment
            if entry_fragment.is_absolute()
            else (pkg_path / entry_fragment)
        )
        try:
            candidate = candidate.resolve()
        except OSError:
            _info(f"Skipping ancillary entry that could not be resolved: {line}")
            continue
        if not candidate.is_relative_to(pkg_path):
            _info(f"Skipping ancillary outside package dir: {line}")
            continue
        if not candidate.is_file():
            _info(f"Skipping non-file ancillary entry: {line}")
            continue
        rel = candidate.relative_to(pkg_path).as_posix()
        if rel not in seen:
            seen.add(rel)
            out.append(rel)
    return out


def _add_ancillary_entry(collected: list[str], seen: set[str], entry: str) -> None:
    if entry not in seen:
        seen.add(entry)
        collected.append(entry)


def _collect_manifest_ancillary(
    pkg_path: Path,
    name: str,
    *,
    seen: set[str],
    collected: list[str],
) -> None:
    safe_name = name.lstrip("/\\")
    candidate = (pkg_path / safe_name).resolve()
    if candidate.is_file():
        rel_path = _safe_rel_from_abs(str(candidate), str(pkg_path))
        if rel_path:
            _add_ancillary_entry(collected, seen, rel_path)
        return
    if candidate.is_dir():
        _info(
            "Ancillary directory provided but not auto-included "
            "(use '@<allowlist>' or opts['ancillary_allowlist']): "
            f"{name}"
        )
        return
    _info(f"Ancillary path not found: {name}")


def _collect_ancillary_files(
    pkg_path: Path,
    ancillary_names: list[str] | None,
) -> list[str]:
    if not ancillary_names:
        return []
    collected: list[str] = []
    seen: set[str] = set()
    pkg_dir_str = str(pkg_path)
    for name in ancillary_names:
        if name.startswith("@"):
            allow_path = pkg_path / name[1:].strip()
            entries = _load_ancillary_allowlist(str(allow_path), pkg_dir_str)
            for rel in entries:
                _add_ancillary_entry(collected, seen, rel)
            continue
        _collect_manifest_ancillary(
            pkg_path,
            name,
            seen=seen,
            collected=collected,
        )
    return collected


def _normalize_publish_path(pkg_path: Path, entry: str) -> str | None:
    candidate = Path(entry)
    resolved = candidate if candidate.is_absolute() else pkg_path / candidate
    try:
        resolved = resolved.resolve()
    except OSError:
        return None
    if resolved.is_dir():
        display = str(resolved)
        if not candidate.is_absolute():
            with suppress(ValueError):
                display = resolved.relative_to(pkg_path).as_posix()
        _info(f"Ignoring ancillary directory (no auto-expansion): {display}")
        return None
    rel = _safe_rel_from_abs(str(resolved), str(pkg_path))
    if not rel:
        return None
    return _to_posix_rel(rel)


def _collect_publish_ancillary(
    pkg_path: Path,
    ancillary_files: list[str] | None,
    safe_kwargs: Mapping[str, object],
) -> list[str]:
    collected: list[str] = []
    seen: set[str] = set()

    for entry in ancillary_files or []:
        if entry.startswith("@"):  # handled via allowlist specs
            continue
        normalized = _normalize_publish_path(pkg_path, entry)
        if normalized:
            _add_ancillary_entry(collected, seen, normalized)

    pkg_dir_str = str(pkg_path)
    for spec in _normalize_allowlist_specs(safe_kwargs):
        spec_path = pkg_path / (spec[1:].strip() if spec.startswith("@") else spec)
        entries = _load_ancillary_allowlist(str(spec_path), pkg_dir_str)
        for rel in entries:
            normalized = _normalize_publish_path(pkg_path, rel)
            if normalized:
                _add_ancillary_entry(collected, seen, normalized)

    if len(collected) > 1:
        collected.sort()
    return collected


def _build_publish_context(
    name: str,
    version: str,
    main_file: str,
    ancillary_files: list[str],
    local_kwargs: dict[str, object],
) -> PublishContext:
    safe_kwargs = {
        key: value
        for key, value in local_kwargs.items()
        if key not in {"dry_run", "cleanup_evidence"}
    }
    main_path = Path(main_file).resolve()
    pkg_path = main_path.parent
    ancillary_rel = _collect_publish_ancillary(
        pkg_path,
        ancillary_files,
        safe_kwargs,
    )
    return PublishContext(
        name=name,
        version=version,
        main_path=main_path,
        pkg_path=pkg_path,
        ancillary_rel=ancillary_rel,
        safe_kwargs=dict(safe_kwargs),
    )


def _repo_base_path(cloner: object, fallback_parent: Path) -> Path:
    base_path = fallback_parent
    target_attr: object = getattr(cloner, "target_dir", None)
    if isinstance(target_attr, str):
        try:
            return Path(target_attr)
        except (TypeError, ValueError):
            return base_path
    if isinstance(target_attr, os.PathLike):
        try:
            return Path(os.fspath(cast("PathLike[str]", target_attr)))
        except (TypeError, ValueError):
            return base_path
    return base_path


def _ensure_package_dir(base_path: Path, pkg: str) -> Path:
    pkg_path = (base_path / pkg).resolve()
    if not pkg_path.is_dir():
        msg = f"Repo package directory not found for {pkg!r} at {pkg_path}"
        raise FileNotFoundError(msg)
    return pkg_path


def _derive_main_basename(pkg: str, main_basename: str | None) -> str:
    if main_basename:
        return main_basename
    return pkg.replace("x_make_", "x_cls_make_") + ".py"


def _discover_main_file(pkg_path: Path, basename: str) -> Path:
    candidate = (pkg_path / basename).resolve()
    if candidate.is_file():
        return candidate
    try:
        children = sorted(pkg_path.iterdir())
    except OSError:
        children = []
    for child in children:
        if (
            child.name.startswith("x_cls_make_")
            and child.suffix == ".py"
            and child.is_file()
        ):
            return child.resolve()
    msg = (
        "Could not locate main file in repo for "
        f"package {pkg_path.name!r} (expected {basename})"
    )
    raise FileNotFoundError(msg)


def _locate_repo_main_and_ancillaries(
    cloner: object,
    pkg: str,
    main_basename: str | None,
    ancillary_names: list[str] | None,
    *,
    fallback_parent: Path,
) -> tuple[str, list[str]]:
    base_path = _repo_base_path(cloner, fallback_parent)
    pkg_path = _ensure_package_dir(base_path, pkg)
    basename = _derive_main_basename(pkg, main_basename)
    main_path = _discover_main_file(pkg_path, basename)
    anc_rel = _collect_ancillary_files(pkg_path, ancillary_names)
    return str(main_path), anc_rel


def _instantiate_publisher(
    publisher_cls: PublisherFactory,
    name: str,
    version: str,
    *,
    ctx: object | None,
    safe_kwargs: dict[str, object],
) -> PublisherProtocol:
    try:
        return publisher_cls(name=name, version=version, ctx=ctx, **safe_kwargs)
    except TypeError:
        pass
    try:
        return publisher_cls(name=name, version=version, **dict(safe_kwargs, ctx=ctx))
    except TypeError:
        pass
    try:
        return publisher_cls(name, version, ctx)
    except TypeError:
        pass
    return publisher_cls(name=name, version=version, **safe_kwargs)


def _execute_publish(
    context: PublishContext,
    ctx: object | None,
    publisher_cls: PublisherFactory,
) -> bool:
    publisher = _instantiate_publisher(
        publisher_cls,
        context.name,
        context.version,
        ctx=ctx,
        safe_kwargs=context.safe_kwargs,
    )
    main_rel = context.main_path.name
    with chdir(context.pkg_path):
        return publisher.publish(main_rel, context.ancillary_rel)


def _should_skip_publish_exception(
    exc: BaseException,
    name: str,
    version: str,
) -> bool:
    message = _exception_summary(exc)
    lowered = message.lower()
    if any(
        marker in lowered
        for marker in (
            "file already exists",
            "400 bad request",
            "file-name-reuse",
            "already exists on pypi",
        )
    ):
        message = (
            f"SKIP: {name} version {version} already exists on PyPI. "
            "Skipping publish."
        )
        _info(message)
        return True
    return False


def _record_publish_result(
    context: PublishContext,
    *,
    published: bool,
    published_versions: dict[str, str | None],
    published_artifacts: dict[str, dict[str, object]],
) -> None:
    published_versions[context.name] = context.version if published else None
    rel_main = _safe_rel_from_abs(str(context.main_path), str(context.pkg_path))
    rel_main = _to_posix_rel(rel_main or context.main_path.name)
    published_artifacts[context.name] = {
        "main": rel_main,
        "anc": context.ancillary_rel,
    }
    if published:
        _info(f"Published {context.name}=={context.version}")
    else:
        _info(f"publish skipped for {context.name} {context.version} (minimal stub)")


def _check_test_pypi(token_env: str = TEST_PYPI_TOKEN_ENV) -> None:
    try:
        token = os.environ.get(token_env)
        url = "https://test.pypi.org/"
        headers = {"Authorization": f"token {token}"} if token else None
        client = HttpClient(timeout=10.0)
        try:
            client.head(url, headers=headers)
        except HttpError as exc:
            message = f"test.pypi.org check failed: {exc}"
            raise AssertionError(message) from exc
        finally:
            with suppress(RuntimeError):
                client.close()
    except AssertionError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        message = f"test.pypi.org check failed: {exc}"
        raise AssertionError(message) from exc


def publish_manifest_entries(  # noqa: PLR0913, PLR0915
    entries: Sequence[ManifestEntry],
    *,
    cloner: object,
    ctx: object | None,
    repo_parent_root: str,
    publisher_factory: PublisherFactory,
    token_env: str = TEST_PYPI_TOKEN_ENV,
) -> tuple[dict[str, str | None], dict[str, dict[str, object]], Path]:
    start_time = datetime.now(UTC)
    run_id = uuid.uuid4().hex
    published_versions: dict[str, str | None] = {}
    published_artifacts: dict[str, dict[str, object]] = {}
    fallback_parent = Path(repo_parent_root).resolve()
    entry_results: list[dict[str, object]] = []
    status = "running"
    caught_exc: Exception | None = None
    report_path: Path

    manifest_inputs: list[dict[str, object]] = [
        {
            "package": entry.package,
            "version": entry.version,
            "pypi_name": entry.options.pypi_name or entry.package,
            "ancillary": list(entry.ancillary),
            "options_kwargs": cast(
                "object", _json_ready(options_to_kwargs(entry.options))
            ),
        }
        for entry in entries
    ]
    publisher_attr_obj = cast(
        "object | None", getattr(publisher_factory, "__name__", None)
    )
    publisher_identifier = (
        publisher_attr_obj
        if isinstance(publisher_attr_obj, str)
        else type(publisher_factory).__name__
    )

    report_payload: dict[str, object] = {
        "run_id": run_id,
        "started_at": isoformat_timestamp(start_time),
        "inputs": {
            "entry_count": len(entries),
            "manifest_entries": manifest_inputs,
            "repo_parent_root": str(repo_parent_root),
            "token_env": token_env,
        },
        "execution": {
            "publisher_factory": publisher_identifier,
        },
        "result": {
            "entries": entry_results,
            "published_versions": published_versions,
            "published_artifacts": published_artifacts,
        },
    }

    _info("Starting the PyPI package publishing process...")
    _check_test_pypi(token_env)

    try:
        for entry in entries:
            repo_name = entry.package
            version = entry.version
            anc_names: list[str] = list(entry.ancillary)
            dist_name = entry.options.pypi_name or repo_name
            main, anc = _locate_repo_main_and_ancillaries(
                cloner,
                repo_name,
                None,
                anc_names,
                fallback_parent=fallback_parent,
            )
            extra_kwargs = options_to_kwargs(entry.options)
            local_kwargs = dict(extra_kwargs)
            local_kwargs["force_publish"] = True
            context = _build_publish_context(
                dist_name,
                version,
                main,
                anc,
                local_kwargs,
            )
            rel_main = _safe_rel_from_abs(str(context.main_path), str(context.pkg_path))
            record: dict[str, object] = {
                "package": repo_name,
                "distribution": context.name,
                "version": context.version,
                "main_file": rel_main or context.main_path.name,
                "ancillary_publish": list(context.ancillary_rel),
                "ancillary_manifest": list(anc_names),
                "package_dir": str(context.pkg_path),
                "safe_kwargs": _json_ready(context.safe_kwargs),
                "status": "pending",
            }
            entry_results.append(record)

            _info(f"Publishing {context.name} version {context.version}")
            try:
                published = _execute_publish(context, ctx, publisher_factory)
                record["status"] = "published"
            except (
                RuntimeError,
                ValueError,
                subprocess.SubprocessError,
                OSError,
            ) as exc:
                if _should_skip_publish_exception(exc, context.name, context.version):
                    published = True
                    record["status"] = "skipped_existing"
                    record["skip_reason"] = _exception_summary(exc)
                else:
                    record["status"] = "error"
                    record["error"] = _exception_summary(exc)
                    _error(f"Failed to publish {context.name}: {exc}")
                    raise
            _record_publish_result(
                context,
                published=published,
                published_versions=published_versions,
                published_artifacts=published_artifacts,
            )

        status = "completed"
        if any(rec.get("status") == "skipped_existing" for rec in entry_results):
            status = "attention"
    except Exception as exc:
        status = "error"
        caught_exc = exc
        raise
    finally:
        end_time = datetime.now(UTC)
        report_payload["status"] = status
        report_payload["completed_at"] = isoformat_timestamp(end_time)
        report_payload["duration_seconds"] = round(
            (end_time - start_time).total_seconds(),
            3,
        )
        report_payload["result"] = {
            "status": status,
            "entries": [_json_ready(entry) for entry in entry_results],
            "published_versions": _json_ready(published_versions),
            "published_artifacts": _json_ready(published_artifacts),
        }
        report_path = write_run_report(
            "x_make_pypi_x",
            report_payload,
            base_dir=PACKAGE_ROOT,
        )
        if caught_exc is not None:
            # Allow the orchestrator to discover the report that captured the
            # failure details without violating strict static analysis.
            exc_dict_raw = cast("object | None", getattr(caught_exc, "__dict__", None))
            if isinstance(exc_dict_raw, dict):
                typed_exc_dict = cast("dict[str, object]", exc_dict_raw)
                typed_exc_dict["run_report_path"] = report_path
    return published_versions, published_artifacts, report_path


def _candidate_release_available(
    client: HttpClient,
    *,
    package_name: str,
    version: str,
    candidate: str,
    attempt_no: int,
) -> bool:
    project_url = f"https://pypi.org/project/{candidate}/{version}/"
    try:
        client.head(project_url)
    except HttpError:
        pass
    else:
        _info(
            "PyPI:",
            (
                f"{package_name}=={version} is now available "
                f"(queried {candidate} via project page)"
            ),
        )
        return True

    json_url = f"https://pypi.org/pypi/{candidate}/json"
    try:
        response = client.get(json_url)
    except HttpError as exc:
        _info(
            "PyPI check attempt",
            attempt_no,
            "for",
            package_name,
            f"(candidate {candidate}) failed:",
            exc,
        )
        return False

    payload = response.json
    if not isinstance(payload, Mapping):
        return False
    typed_payload = cast("Mapping[str, object]", payload)
    releases = typed_payload.get("releases")
    if isinstance(releases, Mapping) and version in releases:
        _info(
            "PyPI:",
            (
                f"{package_name}=={version} is now available "
                f"(queried {candidate} via JSON)"
            ),
        )
        return True
    return False


def wait_for_pypi_release(
    name: str,
    version: str,
    *,
    timeout: int = 120,
    initial_delay: float = 5.0,
    client_timeout: float = 10.0,
) -> bool:
    if timeout <= 0:
        return False
    deadline = time.time() + timeout
    candidates = (name, name.replace("_", "-"))
    sleep_window = min(initial_delay, timeout)
    if sleep_window > 0:
        time.sleep(sleep_window)
    attempt = 0
    backoff = 1.0
    client = HttpClient(timeout=client_timeout)

    last_heartbeat = time.time()
    heartbeat_interval = 5.0

    try:
        while time.time() < deadline:
            attempt += 1
            for candidate in candidates:
                if _candidate_release_available(
                    client,
                    package_name=name,
                    version=version,
                    candidate=candidate,
                    attempt_no=attempt,
                ):
                    return True
            now = time.time()
            if now - last_heartbeat >= heartbeat_interval:
                remaining = max(deadline - now, 0.0)
                emit_event(
                    make_event(
                        source="pypi",
                        phase="wait_release",
                        status="retried",
                        repository=None,
                        tool="x_make_pypi_x",
                        attempt=attempt,
                        duration_ms=None,
                        details={
                            "package": name,
                            "version": version,
                            "attempt": attempt,
                            "seconds_remaining": round(remaining, 1),
                        },
                    )
                )
                last_heartbeat = now
            time.sleep(min(backoff, deadline - time.time()))
            backoff = min(backoff * 2.0, 10.0)
    finally:
        with suppress(RuntimeError):
            client.close()

    _info(
        "Timed out waiting for",
        f"{name}=={version}",
        "on PyPI after",
        timeout,
        "seconds",
    )
    return False


__all__ = [
    "PublishContext",
    "PublisherFactory",
    "PublisherProtocol",
    "options_to_kwargs",
    "publish_manifest_entries",
    "wait_for_pypi_release",
]
