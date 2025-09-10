from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request
import uuid
from typing import Any, Iterable

# Inlined minimal helpers from x_make_common_x.helpers
import logging
import sys as _sys

_LOGGER = logging.getLogger("x_make")


def _info(*args: Any) -> None:
    msg = " ".join(str(a) for a in args)
    try:
        _LOGGER.info("%s", msg)
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        try:
            _sys.stdout.write(msg + "\n")
        except Exception:
            pass


def _error(*args: Any) -> None:
    msg = " ".join(str(a) for a in args)
    try:
        _LOGGER.error("%s", msg)
    except Exception:
        pass
    try:
        print(msg, file=_sys.stderr)
    except Exception:
        try:
            _sys.stderr.write(msg + "\n")
        except Exception:
            try:
                print(msg)
            except Exception:
                pass


# Inlined minimal BaseMake subset used by this module
import os as _os
import subprocess as _subprocess


class BaseMake:
    TOKEN_ENV_VAR: str = "GITHUB_TOKEN"

    @classmethod
    def get_env(cls, name: str, default: Any = None) -> Any:
        return _os.environ.get(name, default)

    @classmethod
    def get_env_bool(cls, name: str, default: bool = False) -> bool:
        v = _os.environ.get(name, None)
        if v is None:
            return default
        return str(v).lower() in ("1", "true", "yes")

    def get_token(self) -> str | None:
        return _os.environ.get(self.TOKEN_ENV_VAR)

    def run_cmd(self, args: Iterable[str], **kwargs: Any) -> _subprocess.CompletedProcess[str]:
        return _subprocess.run(list(args), check=False, capture_output=True, text=True, **kwargs)


"""Twine-backed PyPI publisher implementation (installed shim)."""


class x_cls_make_pypi_x(BaseMake):
    # Configurable endpoints and env names
    PYPI_INDEX_URL: str = "https://pypi.org"
    TEST_PYPI_URL: str = "https://test.pypi.org"
    TEST_PYPI_TOKEN_ENV: str = "TEST_PYPI_TOKEN"

    def version_exists_on_pypi(self) -> bool:
        """Check if the current package name and version already exist on PyPI."""
        try:
            url = f"{self.PYPI_INDEX_URL}/pypi/{self.name}/json"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.load(response)
            return self.version in data.get("releases", {})
        except Exception as e:
            _info(
                f"WARNING: Could not check PyPI for {self.name}=={self.version}: {e}"
            )
            return False

    def __init__(
        self,
        name: str,
        version: str,
        author: str,
        email: str,
        description: str,
        license_text: str,
        dependencies: list[str],
        ctx: object | None = None,
        **kwargs: Any,
    ) -> None:
        # accept optional orchestrator context (backwards compatible)
        self._ctx = ctx

        # store basic metadata
        self.name = name
        self.version = version
        self.author = author
        self.email = email
        self.description = description
        self.license_text = license_text
        self.dependencies = dependencies

        # Prefer ctx-provided dry_run when available (tests expect this)
        try:
            self.dry_run = bool(getattr(self._ctx, "dry_run", False))
        except Exception:
            self.dry_run = False

        self._extra = kwargs or {}
        self.debug = bool(self._extra.get("debug", False))

        # Print preparation message when verbose is requested (or always is OK)
        if getattr(self._ctx, "verbose", False):
            _info(f"[pypi] prepared publisher for {self.name}=={self.version}")

    def update_pyproject_toml(self, project_dir: str) -> None:
        # Intentionally removed: no metadata file manipulation in this publisher.
        # Older behavior updated project metadata here; that logic was removed
        # to ensure this module does not touch or create packaging metadata files.
        return

    def create_files(self, main_file: str, ancillary_files: list[str]) -> None:
        """Create a minimal package tree in a temporary build directory and copy files."""
        package_name = self.name
        repo_build_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "_build_temp_x_pypi_x")
        )
        os.makedirs(repo_build_root, exist_ok=True)
        build_dir = os.path.join(
            repo_build_root, f"_build_{package_name}_{uuid.uuid4().hex}"
        )
        os.makedirs(build_dir, exist_ok=True)
        package_dir = os.path.join(build_dir, package_name)
        if os.path.lexists(package_dir):
            if os.path.isdir(package_dir):
                shutil.rmtree(package_dir)
            else:
                os.remove(package_dir)
        os.makedirs(package_dir, exist_ok=True)

        shutil.copy2(
            main_file, os.path.join(package_dir, os.path.basename(main_file))
        )
        init_path = os.path.join(package_dir, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w", encoding="utf-8") as f:
                f.write("# Package init\n")

        def _is_allowed(p: str) -> bool:
            """Allow-list files copied into the build; avoids mentioning or handling
            any packaging/CI metadata files explicitly.
            """
            # Keep the allow-list intentionally small: source and simple docs.
            _, ext = os.path.splitext(p.lower())
            return ext in {".py", ".txt", ".md", ".rst"} or os.path.basename(p).lower() == "__init__.py"

        # Copy ancillary files but only allow a small set of file types.
        for ancillary_path in ancillary_files or []:
            if os.path.isdir(ancillary_path):
                dest = os.path.join(package_dir, os.path.basename(ancillary_path))
                for root, dirs, files in os.walk(ancillary_path):
                    rel = os.path.relpath(root, ancillary_path)
                    target_root = os.path.join(dest, rel) if rel != "." else dest
                    os.makedirs(target_root, exist_ok=True)
                    for fname in files:
                        srcf = os.path.join(root, fname)
                        if not _is_allowed(srcf):
                            continue
                        shutil.copy2(srcf, os.path.join(target_root, fname))
            elif os.path.isfile(ancillary_path):
                if _is_allowed(ancillary_path):
                    shutil.copy2(
                        ancillary_path,
                        os.path.join(package_dir, os.path.basename(ancillary_path)),
                    )

        self._project_dir = build_dir

    def prepare(self, main_file: str, ancillary_files: list[str]) -> None:
        if not os.path.exists(main_file):
            raise FileNotFoundError(f"Main file '{main_file}' does not exist.")
        for ancillary_file in ancillary_files or []:
            if not os.path.exists(ancillary_file):
                raise FileNotFoundError(
                    f"Ancillary file '{ancillary_file}' is not found."
                )

    def publish(self, main_file: str, ancillary_files: list[str]) -> bool:
        """Build and upload package to PyPI using build + twine.

        Returns True on success; False only for explicit stub behavior.
        """
        # If version already exists, skip
        if self.version_exists_on_pypi():
            _info(
                f"SKIP: {self.name} version {self.version} already exists on PyPI. Skipping publish."
            )
            return True
        self.create_files(main_file, ancillary_files or [])
        project_dir = self._project_dir
        cwd = os.getcwd()
        try:
            os.chdir(project_dir)

            dist_dir = os.path.join(project_dir, "dist")
            if os.path.exists(dist_dir):
                shutil.rmtree(dist_dir)

            build_cmd = [sys.executable, "-m", "build"]
            _info("Running build:", " ".join(build_cmd))
            rc = os.system(" ".join(build_cmd))
            if rc != 0:
                raise RuntimeError("Build failed. Aborting publish.")

            if not os.path.exists(dist_dir):
                raise RuntimeError("dist/ directory not found after build.")

            files = [
                os.path.join(dist_dir, f)
                for f in os.listdir(dist_dir)
                if f.startswith(f"{self.name}-{self.version}")
                and f.endswith((".tar.gz", ".whl"))
            ]
            if not files:
                raise RuntimeError(
                    "No valid distribution files found. Aborting publish."
                )

            pypirc_path = os.path.expanduser("~/.pypirc")
            has_pypirc = os.path.exists(pypirc_path)
            has_env_creds = any(
                [
                    self.get_env("TWINE_USERNAME"),
                    self.get_env("TWINE_PASSWORD"),
                    self.get_env("TWINE_API_TOKEN"),
                ]
            )
            if not has_pypirc and not has_env_creds:
                _info(
                    "WARNING: No PyPI credentials found (.pypirc or TWINE env vars). Upload will likely fail."
                )
            import subprocess

            # Respect an environment toggle to skip uploading files that already
            # exist on PyPI. Default to True to avoid failing the overall run when
            # package files are already present (common in retry scenarios).
            skip_existing = self.get_env_bool("TWINE_SKIP_EXISTING", True)
            if skip_existing:
                twine_cmd = [
                    sys.executable,
                    "-m",
                    "twine",
                    "upload",
                    "--skip-existing",
                    *files,
                ]
                _info("Running upload (with --skip-existing):", " ".join(twine_cmd))
            else:
                twine_cmd = [sys.executable, "-m", "twine", "upload", *files]
                _info("Running upload:", " ".join(twine_cmd))

            result = subprocess.run(
                twine_cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.stdout:
                _info(result.stdout)
            if result.stderr:
                _error(result.stderr)
            if result.returncode != 0:
                raise RuntimeError("Twine upload failed. See output above.")
            return True
        finally:
            try:
                os.chdir(cwd)
            except Exception:
                pass

    def prepare_and_publish(
        self, main_file: str, ancillary_files: list[str]
    ) -> None:
        # Always validate inputs (evidence cleanup is enforced unconditionally).
        self.prepare(main_file, ancillary_files or [])
        self.publish(main_file, ancillary_files or [])


if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
