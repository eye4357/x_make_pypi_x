from __future__ import annotations

import os
import shutil
import stat
import sys
import time
from typing import Any

"""red rabbit 2025_0902_0944"""


class x_cls_make_pypi_x:
    def version_exists_on_pypi(self) -> bool:
        """Check if the current package name and version already exist on PyPI."""
        import json
        import urllib.request

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
    ) -> None:
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

    def update_pyproject_toml(self, project_dir: str) -> None:
        """Update pyproject.toml with the correct name and version before building. Print and validate after update."""
        pyproject_path = os.path.join(project_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            self._essential(f"No pyproject.toml found in {project_dir}, skipping update.")
            return
        with open(pyproject_path, encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
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
        import re

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
        import traceback

        self._debug(f"Attempting to remove: {path}")
        self._print_stat_info(path)
        try:
            if os.path.islink(path):
                os.unlink(path)
            elif os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):

                def _onexc(func, p, exc_info):
                    try:
                        os.chmod(p, stat.S_IWRITE)
                    except Exception:
                        pass
                    try:
                        func(p)
                    except Exception:
                        pass

                shutil.rmtree(path, onexc=_onexc)
        except Exception as e:
            self._essential(f"ERROR: Could not forcibly remove {path}: {e}")
            traceback.print_exc()
        self._debug("After removal attempt:")
        self._print_stat_info(path)

    def _ensure_build_dirs(self) -> tuple[str, str]:
        import uuid

        package_name = self.name
        repo_build_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "_build_temp_x_pypi_x")
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
                    ancillary_path, os.path.join(package_dir, os.path.basename(ancillary_path))
                )

    def _write_pyproject_and_license(self, build_dir: str, package_dir: str) -> None:
        pyproject_path = os.path.join(build_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            spdx_license = (
                "MIT"
                if "MIT" in self.license_text
                else self.license_text.splitlines()[0] if self.license_text else ""
            )
            pyproject_content = (
                f"[project]\n"
                f'name = "{self.name}"\n'
                f'version = "{self.version}"\n'
                f'description = "{self.description}"\n'
                f'authors = [{{name = "{self.author}", email = "{self.email}"}}]\n'
                f'license = "{spdx_license}"\n'
                f"dependencies = {self.dependencies if self.dependencies else []}\n"
            )
            with open(pyproject_path, "w", encoding="utf-8") as f:
                f.write(pyproject_content)
            if self.license_text:
                license_file_path = os.path.join(package_dir, "LICENSE")
                with open(license_file_path, "w", encoding="utf-8") as lf:
                    lf.write(self.license_text)

    def create_files(self, main_file: str, ancillary_files: list[str]) -> None:
        """High-level create_files that orchestrates the smaller helpers."""
        import time

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
        # Ensure pyproject.toml exists and license written
        self._write_pyproject_and_license(build_dir, package_dir)

    def prepare(self, main_file: str, ancillary_files: list[str]) -> None:
        if not os.path.exists(main_file):
            raise FileNotFoundError(f"Main file '{main_file}' does not exist.")
        self._essential(f"Main file found: {main_file}")
        for ancillary_file in ancillary_files:
            if not os.path.exists(ancillary_file):
                self._essential(f"Expected ancillary file not found: {ancillary_file}")
                raise FileNotFoundError(f"Ancillary file '{ancillary_file}' is not found.")
        self._essential("All ancillary files are present.")

    def publish(self, main_file: str, ancillary_files: list[str]) -> None:
        # Check if version already exists on PyPI
        if self.version_exists_on_pypi():
            self._essential(
                f"SKIP: {self.name} version {self.version} already exists on PyPI. Skipping publish."
            )
            return
        # If dry_run is set, skip actual build and upload steps.
        if getattr(self, "dry_run", False):
            self._essential(f"DRY-RUN: Skipping build and upload for {self.name}=={self.version}")
            return
        self.create_files(main_file, ancillary_files)
        self._essential("Main and ancillary files copied. Updating pyproject.toml...")
        project_dir = self._project_dir
        self.update_pyproject_toml(project_dir)
        os.chdir(project_dir)
        # Clean dist/ before build
        dist_dir = os.path.join(project_dir, "dist")
        if os.path.exists(dist_dir):
            self._essential("Cleaning dist/ directory before build...")
            for f in os.listdir(dist_dir):
                try:
                    os.remove(os.path.join(dist_dir, f))
                except Exception as e:
                    self._essential(f"Could not remove {f}: {e}")
        build_cmd = f"{sys.executable} -m build"
        self._essential(f"Running build: {build_cmd}")
        build_result = os.system(build_cmd)
        if build_result != 0:
            self._essential("Build failed.")
            raise RuntimeError("Build failed. Aborting publish.")
        if not os.path.exists(dist_dir):
            self._essential("dist/ directory not found after build.")
            raise RuntimeError("dist/ directory not found. Aborting publish.")
        # Only upload files matching package name and version
        files = self._collect_dist_files(dist_dir)
        self._run_twine_upload(files)

    def _run_twine_upload(self, files: list[str]) -> None:
        files_str = " ".join([f'"{f}"' for f in files])
        pypirc_path = os.path.expanduser("~/.pypirc")
        has_pypirc = os.path.exists(pypirc_path)
        has_env_creds = any(
            [
                os.environ.get("TWINE_USERNAME"),
                os.environ.get("TWINE_PASSWORD"),
                os.environ.get("TWINE_API_TOKEN"),
            ]
        )
        if not has_pypirc and not has_env_creds:
            self._essential(
                "WARNING: No PyPI credentials found (.pypirc or TWINE env vars). Upload will likely fail."
            )
        twine_cmd = f"{sys.executable} -m twine upload {files_str} --verbose"
        self._essential(f"Running upload: {twine_cmd}")
        import subprocess

        try:
            result = subprocess.run(
                twine_cmd, check=False, shell=True, capture_output=True, text=True
            )
            self._debug("Twine stdout:")
            self._debug(result.stdout)
            self._debug("Twine stderr:")
            self._debug(result.stderr)
            if result.returncode != 0:
                self._essential(f"Upload to PyPI failed with exit code {result.returncode}.")
                raise RuntimeError("Twine upload failed. See output above.")
            else:
                self._essential("Upload to PyPI succeeded.")
        except Exception as e:
            self._essential(f"Exception during Twine upload: {e}")
            raise

    def _collect_dist_files(self, dist_dir: str) -> list[str]:
        """Return a list of files in dist_dir that match the package name and version."""
        matches: list[str] = []
        if not os.path.isdir(dist_dir):
            return matches
        for fname in os.listdir(dist_dir):
            if self.name in fname and self.version in fname:
                matches.append(os.path.join(dist_dir, fname))
        return matches

    def prepare_and_publish(self, main_file: str, ancillary_files: list[str]) -> None:
        if self.cleanup_evidence:
            self.prepare(main_file, ancillary_files)
        self.publish(main_file, ancillary_files)
        if self.cleanup_evidence:
            self.prepare(main_file, ancillary_files)


if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
