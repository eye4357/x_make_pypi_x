from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import uuid
from typing import Any

"""red rabbit 2025_0902_0944"""


class x_cls_make_pypi_x:
    def version_exists_on_pypi(self) -> bool:
        """Check if the current package name and version already exist on PyPI."""
        url = f"https://pypi.org/pypi/{self.name}/json"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.load(response)
            return self.version in data.get("releases", {})
        except Exception as e:
            # Always show this as an essential warning
            try:
                self._essential(
                    f"WARNING: Could not check PyPI for {self.name}=={self.version}: {e}"
                )
            except Exception:
                # If called before initialization of helpers, fall back to print
                print(f"WARNING: Could not check PyPI for {self.name}=={self.version}: {e}")
            return False

    """
    Minimal PyPI publisher: Only copies the main file, ancillary files, and preserves CI files. No legacy packaging files are created or required.
    """

    def _essential(self, *args: Any, **kwargs: Any) -> None:
        """Always-printed messages (errors, warnings, high-level status)."""
        print(*args, **kwargs)

    def _debug(self, *args: Any, **kwargs: Any) -> None:
        """Verbose diagnostic output printed only when self.debug is True."""
        if getattr(self, "debug", False):
            print(*args, **kwargs)

    def __init__(
        self,
        name: str,
        version: str,
        author: str,
        email: str,
        description: str,
        license_text: str,
        dependencies: list[str],
        cleanup_evidence: bool = True,
        dry_run: bool = False,
        debug: bool = False,
        auto_install_twine: bool = False,
    ) -> None:
        """Initialize publisher state.

        All attributes are stored on self so other methods can reference them.
        """
        self.name = name
        self.version = version
        self.author = author
        self.email = email
        self.description = description
        self.license_text = license_text
        self.dependencies = dependencies
        self.cleanup_evidence = cleanup_evidence
        self.dry_run = dry_run
        # Controls verbose diagnostic printing across the class
        self.debug = debug
        # If True, attempt to pip install twine automatically when missing
        self.auto_install_twine = auto_install_twine

    def update_pyproject_toml(self, project_dir: str) -> None:
        """Update pyproject.toml with the correct name and version before building. Print and validate after update."""
        pyproject_path = os.path.join(project_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            self._essential(f"No pyproject.toml found in {project_dir}, skipping update.")
            return
        with open(pyproject_path, encoding="utf-8") as f:
            lines = f.readlines()
        new_lines: list[str] = []
        in_project_section = False
        project_section_found = False
        for line in lines:
            ln = line
            if line.strip().lower() == "[project]":
                in_project_section = True
                project_section_found = True
                new_lines.append(line)
                continue
            if in_project_section:
                if line.strip().startswith("name ="):
                    ln = f'name = "{self.name}"\n'
                elif line.strip().startswith("version ="):
                    ln = f'version = "{self.version}"\n'
                elif line.strip() == "" or line.strip().startswith("["):
                    in_project_section = False
            new_lines.append(ln)
        # If no [project] section, add it
        if not project_section_found:
            new_lines.append("\n[project]\n")
            new_lines.append(f'name = "{self.name}"\n')
            new_lines.append(f'version = "{self.version}"\n')
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        self._essential(f"Updated pyproject.toml with name={self.name}, version={self.version}")
        # Print and validate pyproject.toml
        with open(pyproject_path, encoding="utf-8") as f:
            contents = f.read()
        self._debug("pyproject.toml after update:")
        self._debug(contents)
        # Validate [project] section
        name_match = re.search(r'^name\s*=\s*"(.+)"', contents, re.MULTILINE)
        version_match = re.search(r'^version\s*=\s*"(.+)"', contents, re.MULTILINE)
        if not name_match or not name_match.group(1).strip():
            raise RuntimeError(
                "pyproject.toml missing or empty 'name' in [project] section after update."
            )
        if not version_match or not version_match.group(1).strip():
            raise RuntimeError(
                "pyproject.toml missing or empty 'version' in [project] section after update."
            )

    def _print_stat_info(self, path: str) -> None:
        self._debug(f"STAT: {path}")
        self._debug(f"  Exists: {os.path.lexists(path)}")
        self._debug(f"  Symlink: {os.path.islink(path)}")
        self._debug(f"  File: {os.path.isfile(path)}")
        self._debug(f"  Dir: {os.path.isdir(path)}")
        try:
            self._debug(f"  Stat: {os.stat(path)}")
        except Exception as e:
            self._debug(f"  Stat failed: {e}")

    def _force_remove_any(self, path: str) -> None:
        # traceback is imported at module level for diagnostic printing
        self._debug(f"Attempting to remove: {path}")
        self._print_stat_info(path)
        try:
            if os.path.islink(path):
                os.unlink(path)
            elif os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):

                def _onexc(func: Any, p: str, exc_info: Any) -> None:
                    """Compatibility onexc/onerror handler: make path writable and retry the operation."""
                    try:
                        os.chmod(p, stat.S_IWRITE)
                    except Exception:
                        pass
                    try:
                        func(p)
                    except Exception:
                        pass

                # Prefer the modern `onexc` parameter when available (Python 3.13+).
                # Fall back to the older `onerror` name for compatibility, then to a plain rmtree.
                try:
                    shutil.rmtree(path, onexc=_onexc)  # modern API (preferred)
                except TypeError:
                    # onexc not supported; fall back to plain rmtree
                    try:
                        shutil.rmtree(path)
                    except Exception:
                        pass
                except Exception:
                    # Any other error: attempt plain rmtree as a last resort
                    try:
                        shutil.rmtree(path)
                    except Exception:
                        pass
        except Exception as e:
            self._essential(f"ERROR: Could not forcibly remove {path}: {e}")
            traceback.print_exc()
        self._debug("After removal attempt:")
        self._print_stat_info(path)

    def _ensure_build_dirs(self) -> tuple[str, str]:
        package_name = self.name
        # Use system temporary directory to avoid creating transient build
        # artifacts inside repository trees (which confuse mypy/pre-commit).
        repo_build_root = os.path.abspath(
            os.path.join(tempfile.gettempdir(), "_build_temp_x_pypi_x")
        )
        os.makedirs(repo_build_root, exist_ok=True)
        build_dir = os.path.join(repo_build_root, f"_build_{package_name}_{uuid.uuid4().hex}")
        os.makedirs(build_dir, exist_ok=True)
        package_dir = os.path.join(build_dir, package_name)
        return build_dir, package_dir

    def _create_package_dir(self, build_dir: str, package_dir: str) -> None:
        # Remove and verify both build_dir and package_dir
        for path in [package_dir, build_dir]:
            if os.path.lexists(path):
                self._force_remove_any(path)
                if os.path.lexists(path):
                    self._essential(
                        f"FATAL: {path} still exists after attempted removal. Aborting."
                    )
                    raise RuntimeError(f"Could not remove: {path}")

        # Recreate build dir
        os.makedirs(build_dir, exist_ok=True)

        # Remove any file/folder/symlink named package_dir before creation
        if os.path.lexists(package_dir):
            self._debug(f"DIAGNOSTIC: {package_dir} exists before creation.")
            self._print_stat_info(package_dir)
            self._force_remove_any(package_dir)
            time.sleep(1)
            if os.path.lexists(package_dir):
                self._essential(
                    f"WARNING: {package_dir} still exists after first forced removal and delay."
                )
                self._print_stat_info(package_dir)
                self._debug("Attempting final forced removal and longer delay...")
                self._force_remove_any(package_dir)
                time.sleep(2)
                if os.path.lexists(package_dir):
                    self._essential(
                        f"FATAL: {package_dir} still exists after final forced removal and delay."
                    )
                    self._print_stat_info(package_dir)
                    self._essential("Contents of parent build directory:")
                    for item in os.listdir(build_dir):
                        self._essential(f" - {item}")
                    raise RuntimeError(f"Could not remove package_dir: {package_dir}")

        self._debug(f"DIAGNOSTIC: About to create {package_dir} if needed.")
        self._print_stat_info(package_dir)
        if not os.path.exists(package_dir):
            try:
                os.makedirs(package_dir, exist_ok=True)
            except OSError as e:
                self._essential(f"FATAL: Could not create {package_dir}: {e}")
                self._print_stat_info(package_dir)
                if os.path.lexists(package_dir):
                    self._essential("Contents of parent build directory:")
                    for item in os.listdir(build_dir):
                        self._essential(f" - {item}")
                raise
        else:
            self._essential(f"INFO: {package_dir} already exists as a directory, proceeding.")

    def _copy_main_and_ancillary(
        self, main_file: str, ancillary_files: list[str], package_dir: str
    ) -> None:
        # Copy main file
        shutil.copy2(main_file, os.path.join(package_dir, os.path.basename(main_file)))
        # Ensure __init__.py exists
        init_path = os.path.join(package_dir, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w", encoding="utf-8") as f:
                f.write("# Package init\n")
        # Copy ancillary files/folders into package dir
        for ancillary_path in ancillary_files:
            if os.path.isdir(ancillary_path):
                dest = os.path.join(package_dir, os.path.basename(ancillary_path))
                if os.path.lexists(dest):
                    self._debug(
                        f"DIAGNOSTIC: Ancillary destination {dest} exists before copy. Removing..."
                    )
                    self._print_stat_info(dest)
                    self._force_remove_any(dest)
                    time.sleep(0.5)
                shutil.copytree(ancillary_path, dest)
            elif os.path.isfile(ancillary_path):
                shutil.copy2(
                    ancillary_path,
                    os.path.join(package_dir, os.path.basename(ancillary_path)),
                )

    def _write_pyproject_and_license(self, build_dir: str, package_dir: str) -> None:
        pyproject_path = os.path.join(build_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            spdx_license = (
                "MIT"
                if "MIT" in self.license_text
                else self.license_text.splitlines()[0] if self.license_text else ""
            )
            # Generate a minimal pyproject.toml that uses setuptools as the
            # build backend and configures setuptools to discover packages and
            # include package data. This ensures non-Python ancillary files
            # copied into the package directory are included in the wheel/sdist.
            pyproject_content = (
                "[build-system]\n"
                'requires = ["setuptools>=61", "wheel"]\n'
                'build-backend = "setuptools.build_meta"\n\n'
                "[project]\n"
                f'name = "{self.name}"\n'
                f'version = "{self.version}"\n'
                f'description = "{self.description}"\n'
                f'authors = [{{name = "{self.author}", email = "{self.email}"}}]\n'
                f'license = "{spdx_license}"\n'
                f"dependencies = {self.dependencies if self.dependencies else []}\n\n"
                "[tool.setuptools]\n"
                "include-package-data = true\n\n"
                "[tool.setuptools.packages.find]\n"
                'where = ["."]\n'
            )
            with open(pyproject_path, "w", encoding="utf-8") as f:
                f.write(pyproject_content)
            # Write LICENSE both inside the package (for package-level visibility)
            # and at the project root so sdist metadata includes it.
            if self.license_text:
                license_file_path_pkg = os.path.join(package_dir, "LICENSE")
                try:
                    with open(license_file_path_pkg, "w", encoding="utf-8") as lf:
                        lf.write(self.license_text)
                except Exception:
                    pass
                license_file_path_root = os.path.join(build_dir, "LICENSE")
                try:
                    with open(license_file_path_root, "w", encoding="utf-8") as lf:
                        lf.write(self.license_text)
                except Exception:
                    pass

    def create_files(self, main_file: str, ancillary_files: list[str]) -> None:
        """High-level create_files that orchestrates the smaller helpers."""
        # time is imported at module level; no local import required
        build_dir, package_dir = self._ensure_build_dirs()
        self._create_package_dir(build_dir, package_dir)
        # Copy files into package dir
        self._copy_main_and_ancillary(main_file, ancillary_files, package_dir)
        # Final verification: ensure package_dir is a directory
        self._debug(f"DIAGNOSTIC: After ancillary file copy, checking {package_dir}.")
        self._print_stat_info(package_dir)
        if os.path.lexists(package_dir) and not os.path.isdir(package_dir):
            self._essential(
                f"WARNING: {package_dir} is not a directory after ancillary file copy. Forcing removal."
            )
            self._force_remove_any(package_dir)
            time.sleep(1)
            if os.path.lexists(package_dir):
                self._essential(
                    f"FATAL: {package_dir} still exists after forced removal post ancillary copy."
                )
                self._print_stat_info(package_dir)
                raise RuntimeError(f"Could not ensure package_dir is a directory: {package_dir}")
        # Set project_dir for build/publish
        self._project_dir = build_dir
        # Ensure developer/config files are present in the project root
        self._write_dev_configs(build_dir, package_dir)
        # Ensure pyproject.toml exists and license written
        self._write_pyproject_and_license(build_dir, package_dir)

    def _write_dev_configs(self, build_dir: str, package_dir: str) -> None:
        """Write dev tooling files into the build/project root.

        These are created only inside the temporary build directory used for
        packaging so existing repositories are not modified.
        """
        # Delegate to the smaller helper functions. Keep this method tiny so
        # linters don't report very-high complexity. The helpers perform
        # idempotent writes and are safe to call repeatedly.
        os.makedirs(build_dir, exist_ok=True)
        self._write_precommit_file(build_dir)
        self._write_ci_workflow(build_dir)
        self._write_misc_files(build_dir)

    def prepare(self, main_file: str, ancillary_files: list[str]) -> None:
        if not os.path.exists(main_file):
            raise FileNotFoundError(f"Main file '{main_file}' does not exist.")
        self._essential(f"Main file found: {main_file}")
        for ancillary_file in ancillary_files:
            if not os.path.exists(ancillary_file):
                self._essential(f"Expected ancillary file not found: {ancillary_file}")
                raise FileNotFoundError(f"Ancillary file '{ancillary_file}' is not found.")
        self._essential("All ancillary files are present.")

    def prepare_and_publish(self, main_file: str, ancillary_files: list[str]) -> None:
        """Compatibility wrapper: older orchestrator calls expect prepare_and_publish.

        This runs the two-step flow: validate files (prepare) then build/publish (publish).
        """
        # Prepare may raise FileNotFoundError for missing files; let exceptions propagate
        self.prepare(main_file, ancillary_files)
        # Publish will perform build and (optionally) upload
        self.publish(main_file, ancillary_files)

    # --- Smaller helpers to keep `publish` simple and reduce complexity ---
    def _already_published(self) -> bool:
        """Return True and log if the current name/version exist on PyPI."""
        if self.version_exists_on_pypi():
            self._essential(
                f"SKIP: {self.name} version {self.version} already exists on PyPI. Skipping publish."
            )
            return True
        return False

    def _is_dry_run(self) -> bool:
        if getattr(self, "dry_run", False):
            self._essential(f"DRY-RUN: Skipping build and upload for {self.name}=={self.version}")
            return True
        return False

    def _prepare_project_dir(self, main_file: str, ancillary_files: list[str]) -> str:
        """Create temporary project files, update pyproject and chdir into project."""
        self.create_files(main_file, ancillary_files)
        self._essential("Main and ancillary files copied. Updating pyproject.toml...")
        project_dir = self._project_dir
        # write dev/config files in the project root
        self._write_precommit_file(project_dir)
        self._write_ci_workflow(project_dir)
        self._write_misc_files(project_dir)
        self.update_pyproject_toml(project_dir)
        os.chdir(project_dir)
        return project_dir

    def _clean_dist_dir(self, project_dir: str) -> None:
        dist_dir = os.path.join(project_dir, "dist")
        if os.path.exists(dist_dir):
            self._debug(f"Removing existing dist/ at {dist_dir}")
            try:
                self._force_remove_any(dist_dir)
            except Exception:
                pass

    def _run_build(self) -> None:
        build_cmd = [sys.executable, "-m", "build", "--sdist", "--wheel"]
        self._essential(f"Building distributions for {self.name}=={self.version}")
        self._debug(f"Build command: {' '.join(build_cmd)}")
        if getattr(self, "dry_run", False):
            self._essential("DRY-RUN: Skipping build command")
            return
        try:
            proc = subprocess.run(build_cmd, check=True, capture_output=not self.debug, text=True)
            if self.debug:
                self._debug(proc.stdout or "", proc.stderr or "")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Build failed for {self.name}: {e}") from e

    def _ensure_twine_available(self) -> bool:
        """Return True if twine is importable or was successfully installed (when allowed)."""
        try:

            return True
        except Exception:
            pass

        if not getattr(self, "auto_install_twine", False):
            return False

        self._essential(
            "Twine not found; attempting to install twine in the current environment..."
        )
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "twine"],
                check=True,
            )
            # Try importing again after install
            try:

                return True
            except Exception:
                return False
        except Exception as e:
            self._essential(f"Automatic twine install failed: {e}")
            return False

    def _run_upload(self) -> None:
        upload_cmd = [sys.executable, "-m", "twine", "upload", "dist/*"]
        self._essential(f"Uploading {self.name}=={self.version} to PyPI using twine")
        self._debug(f"Upload command: {' '.join(upload_cmd)}")
        try:
            proc = subprocess.run(upload_cmd, check=True, capture_output=not self.debug, text=True)
            if self.debug:
                self._debug(proc.stdout or "", proc.stderr or "")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Upload failed for {self.name}: {e}") from e

    def publish(self, main_file: str, ancillary_files: list[str]) -> None:
        # Minimal publish flow: delegate work to small helpers to keep complexity low.
        if self._already_published():
            return

        if self._is_dry_run():
            return

        project_dir = self._prepare_project_dir(main_file, ancillary_files)
        self._clean_dist_dir(project_dir)
        # Build distributions
        self._run_build()

        # After build, if this is a dry-run we would have returned earlier.
        # Ensure twine is available (optionally auto-install) and upload.
        if not self._ensure_twine_available():
            self._essential(
                f"Build complete for {self.name}=={self.version}; twine not available so upload was skipped."
            )
            self._essential(
                "To upload manually, install twine and run: python -m twine upload dist/*"
            )
            return

        # Upload using twine
        self._run_upload()
        self._essential(f"Published {self.name}=={self.version}")

    # Clean dist/ before build (dist dir handled by build tool when invoked)

    def _write_precommit_file(self, build_dir: str) -> None:
        precommit = os.path.join(build_dir, ".pre-commit-config.yaml")
        if os.path.exists(precommit):
            return
        try:
            with open(precommit, "w", encoding="utf-8") as f:
                f.write(
                    """repos:\n  - repo: https://github.com/pre-commit/pre-commit-hooks\n    rev: v4.6.0\n    hooks:\n      - id: trailing-whitespace\n      - id: end-of-file-fixer\n      - id: check-yaml\n      - id: check-toml\n  - repo: https://github.com/astral-sh/ruff\n    rev: stable\n    hooks:\n      - id: ruff\n  - repo: https://github.com/psf/black\n    rev: stable\n    hooks:\n      - id: black\n  - repo: https://github.com/python/mypy\n    rev: stable\n    hooks:\n      - id: mypy\n"""
                )
        except Exception:
            pass

    def _write_ci_workflow(self, build_dir: str) -> None:
        gh_dir = os.path.join(build_dir, ".github", "workflows")
        os.makedirs(gh_dir, exist_ok=True)
        ci_path = os.path.join(gh_dir, "ci.yml")
        if os.path.exists(ci_path):
            return
        try:
            with open(ci_path, "w", encoding="utf-8") as f:
                f.write(
                    """name: CI\n\non: [push, pull_request]\n\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - name: Set up Python\n        uses: actions/setup-python@v4\n        with:\n          python-version: '3.x'\n      - name: Install deps\n        run: pip install ruff black mypy\n      - name: Run ruff\n        run: ruff check .\n      - name: Run black check\n        run: black --check .\n      - name: Run mypy\n        run: mypy .\n"""
                )
        except Exception:
            pass

    def _write_misc_files(self, build_dir: str) -> None:
        gitignore = os.path.join(build_dir, ".gitignore")
        if not os.path.exists(gitignore):
            try:
                with open(gitignore, "w", encoding="utf-8") as f:
                    f.write(".venv\n__pycache__\n.build\n.dist-info\nbuild/\ndist/\n")
            except Exception:
                pass

        reqs = os.path.join(build_dir, "requirements-dev.txt")
        if not os.path.exists(reqs):
            try:
                with open(reqs, "w", encoding="utf-8") as f:
                    f.write("ruff\nblack\nmypy\n")
            except Exception:
                pass

        scripts_dir = os.path.join(build_dir, "scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        ps1 = os.path.join(scripts_dir, "bootstrap_dev.ps1")
        bat = os.path.join(scripts_dir, "bootstrap_dev.bat")
        if not os.path.exists(ps1):
            try:
                with open(ps1, "w", encoding="utf-8") as f:
                    f.write(
                        "# PowerShell bootstrap: install dev tools\n"
                        "python -m pip install --upgrade pip\n"
                        "python -m pip install -r requirements-dev.txt\n"
                        "pre-commit install\n"
                    )
            except Exception:
                pass
        if not os.path.exists(bat):
            try:
                with open(bat, "w", encoding="utf-8") as f:
                    f.write(
                        "@echo off\n"
                        "python -m pip install --upgrade pip\n"
                        "python -m pip install -r requirements-dev.txt\n"
                        "pre-commit install\n"
                    )
            except Exception:
                pass

        readme = os.path.join(build_dir, "README.md")
        if not os.path.exists(readme):
            try:
                with open(readme, "w", encoding="utf-8") as f:
                    f.write(f"# {self.name}\n\n{self.description}\n")
            except Exception:
                pass
        # Create a MANIFEST.in so setuptools includes ancillary files copied
        # into the package directory in both sdist and wheel builds. This is
        # important for packages like x_make_markdown_x that ship non-Python
        # files or subdirectories inside the package directory.
        manifest = os.path.join(build_dir, "MANIFEST.in")
        try:
            pkg_dir = os.path.join(build_dir, self.name)
            lines: list[str] = []
            if os.path.exists(pkg_dir) and os.path.isdir(pkg_dir):
                # Include everything under the package directory
                lines.append(f"recursive-include {self.name} *\n")
            # Make sure LICENSE and README are included in source distributions
            lines.append("global-include LICENSE\n")
            lines.append("global-include README.md\n")
            with open(manifest, "w", encoding="utf-8") as mf:
                mf.writelines(lines)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
