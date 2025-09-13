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
import subprocess as _subprocess

_LOGGER = logging.getLogger("x_make")
_os = os


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
        pass


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

    def run_cmd(
        self, args: Iterable[str], **kwargs: Any
    ) -> _subprocess.CompletedProcess[str]:
        return _subprocess.run(
            list(args), check=False, capture_output=True, text=True, **kwargs
        )


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

    def ensure_type_metadata(
        self,
        repo_name: str,
        base_dir: str,
        ancillary_files: list[str] | None = None,
    ) -> None:
        """Inject PEP 561 artifacts and minimal build metadata without recursion."""
        try:
            from pathlib import Path as _P

            pkg_path = _P(base_dir)  # build_dir/<dist_name>
            bd = _P(repo_name)  # build_dir (project root)

            py_typed = pkg_path / "py.typed"
            if not py_typed.exists():
                try:
                    py_typed.write_text("", encoding="utf-8")
                except Exception:
                    return

            # MANIFEST.in: only explicit includes under the package path
            manifest_lines: list[str] = [
                f"include {pkg_path.name}/py.typed",
            ]
            for a in ancillary_files or []:
                try:
                    rel = a.replace("\\", "/").lstrip("/")
                    if (pkg_path / rel).is_file():
                        manifest_lines.append(f"include {pkg_path.name}/{rel}")
                except Exception:
                    continue
            man_path = bd / "MANIFEST.in"
            try:
                man_path.write_text(
                    "\n".join(dict.fromkeys(manifest_lines)) + "\n",
                    encoding="utf-8",
                )
            except Exception:
                pass

            # pyproject: enable package-data, but no recursive globs
            pyproject = bd / "pyproject.toml"
            try:
                base_pyproject = (
                    "[build-system]\n"
                    'requires = ["setuptools", "wheel"]\n'
                    'build-backend = "setuptools.build_meta"\n\n'
                    "[project]\n"
                    f'name = "{self.name}"\n'
                    f'version = "{self.version}"\n'
                    f'description = "{self.description or f"Package {self.name}"}"\n'
                    'requires-python = ">=3.8"\n'
                )
                if self.author or self.email:
                    auth_name = self.author or "Unknown"
                    auth_email = self.email or "unknown@example.com"
                    base_pyproject += f'authors = [{{name = "{auth_name}", email = "{auth_email}"}}]\n'
                if self.dependencies:
                    deps_serial = ",\n    ".join(
                        f'"{d}"' for d in self.dependencies
                    )
                    base_pyproject += (
                        f"dependencies = [\n    {deps_serial}\n]\n"
                    )

                base_pyproject += (
                    "\n[tool.setuptools]\ninclude-package-data = true\n"
                    '\n[tool.setuptools.packages.find]\nwhere = ["."]\n'
                    f'include = ["{pkg_path.name}"]\n'
                    "\n[tool.setuptools.package-data]\n"
                    f'{pkg_path.name} = ["py.typed"]\n'
                )
                if not pyproject.exists():
                    pyproject.write_text(base_pyproject, encoding="utf-8")
                else:
                    txt = pyproject.read_text(encoding="utf-8")
                    changed = False
                    if "include-package-data" not in txt:
                        if "[tool.setuptools]" in txt:
                            txt += "\ninclude-package-data = true\n"
                        else:
                            txt += "\n[tool.setuptools]\ninclude-package-data = true\n"
                        changed = True
                    if "[tool.setuptools.package-data]" not in txt:
                        txt += f'\n[tool.setuptools.package-data]\n{pkg_path.name} = ["py.typed"]\n'
                        changed = True
                    if "[tool.setuptools.packages.find]" not in txt:
                        txt += '\n[tool.setuptools.packages.find]\nwhere = ["."]\n'
                        changed = True
                    if "name =" not in txt or "version =" not in txt:
                        txt += "\n" + base_pyproject
                        changed = True
                    if changed:
                        pyproject.write_text(txt, encoding="utf-8")
            except Exception:
                pass
        except Exception:
            pass

    def create_files(self, main_file: str, ancillary_files: list[str]) -> None:
        """
        Create a minimal package tree in a temporary build directory and
        copy files.
        """
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
            """Allow-list files copied into the build."""
            _, ext = os.path.splitext(p.lower())
            allowed = {".py", ".txt", ".md", ".rst"}
            return (
                ext in allowed or os.path.basename(p).lower() == "__init__.py"
            )

        # Copy ancillaries: files only; do not recurse directories
        for entry in ancillary_files or []:
            rel_norm = entry.replace("\\", "/").lstrip("/")
            src_path = rel_norm.replace("/", os.sep)
            if os.path.isdir(src_path):
                _info(
                    f"Ignoring ancillary directory (no recursion): {rel_norm}"
                )
                continue
            if os.path.isfile(src_path) and _is_allowed(src_path):
                dest_path = os.path.join(package_dir, src_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)

        # Ensure lightweight stub files (.pyi) exist for typing in every
        # package directory and for each copied module. These are minimal
        # and safe: they do not attempt to reconstruct full signatures, but
        # provide a place-holder so downstream tools won't fail to find stubs.
        try:
            for root, _dirs, files in os.walk(package_dir):
                # package-level stub
                pyi_init = os.path.join(root, "__init__.pyi")
                if not os.path.exists(pyi_init):
                    try:
                        with open(pyi_init, "w", encoding="utf-8") as f:
                            f.write(
                                f"# Type stubs for package {os.path.basename(root)}\nfrom typing import Any\n\n__all__: list[str]\n"
                            )
                    except Exception:
                        pass

                # module-level stubs for any .py files
                for fname in files:
                    if fname.endswith(".py") and not fname.endswith(".pyi"):
                        stub_path = os.path.join(root, fname[:-3] + ".pyi")
                        if not os.path.exists(stub_path):
                            try:
                                with open(
                                    stub_path, "w", encoding="utf-8"
                                ) as f:
                                    f.write(
                                        f"# Stub for {fname}\nfrom typing import Any\n\n"
                                    )
                            except Exception:
                                pass
        except Exception:
            # Best-effort: do not fail the build just because stubs couldn't be written.
            pass

        # After stubs generated, ensure PEP 561 artifacts & metadata
        try:
            self.ensure_type_metadata(build_dir, package_dir, ancillary_files)
        except Exception:
            pass
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
            msg = (
                f"SKIP: {self.name} version {self.version} already "
                "exists on PyPI. Skipping publish."
            )
            _info(msg)
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
                    "WARNING: No PyPI credentials found (.pypirc or TWINE env vars)."
                    " Upload will likely fail."
                )

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
                _info(
                    "Running upload (with --skip-existing):",
                    " ".join(twine_cmd),
                )
            else:
                twine_cmd = [sys.executable, "-m", "twine", "upload", *files]
                _info("Running upload:", " ".join(twine_cmd))

            result = _subprocess.run(
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
