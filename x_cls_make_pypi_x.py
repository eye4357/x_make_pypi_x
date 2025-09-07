from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request
import uuid
from typing import Any


# Minimal BaseMake fallback so this module works even if
# x_make_common_x is not present in the environment. This mirrors the
# small surface area used by the publisher (get_env/get_env_bool/run_cmd).
class BaseMake:
    def get_env(self, name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, default)

    def get_env_bool(self, name: str, default: bool = False) -> bool:
        v = os.environ.get(name)
        if v is None:
            return default
        return v.lower() in ("1", "true", "yes")


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
            print(
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
        cleanup_evidence: bool = True,
        dry_run: bool = False,
        **kwargs: Any,
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
        self._extra = kwargs or {}
        self.debug = bool(self._extra.get("debug", False))

    def update_pyproject_toml(self, project_dir: str) -> None:
        pyproject_path = os.path.join(project_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            print(
                f"No pyproject.toml found in {project_dir}, skipping update."
            )
            return
        with open(pyproject_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        in_project_section = False
        project_section_found = False
        for line in lines:
            if line.strip().lower() == "[project]":
                in_project_section = True
                project_section_found = True
                new_lines.append(line)
                continue
            if in_project_section:
                if line.strip().startswith("name ="):
                    line = f'name = "{self.name}"\n'
                elif line.strip().startswith("version ="):
                    line = f'version = "{self.version}"\n'
                elif line.strip() == "" or line.strip().startswith("["):
                    in_project_section = False
            new_lines.append(line)
        if not project_section_found:
            new_lines.append("\n[project]\n")
            new_lines.append(f'name = "{self.name}"\n')
            new_lines.append(f'version = "{self.version}"\n')
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(
            f"Updated pyproject.toml with name={self.name}, version={self.version}"
        )

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

        for ancillary_path in ancillary_files or []:
            if os.path.isdir(ancillary_path):
                dest = os.path.join(
                    package_dir, os.path.basename(ancillary_path)
                )
                shutil.copytree(ancillary_path, dest)
            elif os.path.isfile(ancillary_path):
                shutil.copy2(
                    ancillary_path,
                    os.path.join(
                        package_dir, os.path.basename(ancillary_path)
                    ),
                )

        self._project_dir = build_dir

        pyproject_path = os.path.join(build_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            spdx_license = (
                "MIT"
                if "MIT" in self.license_text
                else (
                    self.license_text.splitlines()[0]
                    if self.license_text
                    else ""
                )
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
            print(
                f"SKIP: {self.name} version {self.version} already exists on PyPI. Skipping publish."
            )
            return True

        self.create_files(main_file, ancillary_files or [])
        project_dir = self._project_dir
        self.update_pyproject_toml(project_dir)
        os.chdir(project_dir)

        dist_dir = os.path.join(project_dir, "dist")
        if os.path.exists(dist_dir):
            shutil.rmtree(dist_dir)

        build_cmd = [sys.executable, "-m", "build"]
        print("Running build:", " ".join(build_cmd))
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
            print(
                "WARNING: No PyPI credentials found (.pypirc or TWINE env vars). Upload will likely fail."
            )

        twine_cmd = [sys.executable, "-m", "twine", "upload"] + files
        print("Running upload:", " ".join(twine_cmd))
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "twine", "upload"] + files,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        print(result.stderr)
        if result.returncode != 0:
            raise RuntimeError("Twine upload failed. See output above.")
        return True

    def prepare_and_publish(
        self, main_file: str, ancillary_files: list[str]
    ) -> None:
        if self.cleanup_evidence:
            self.prepare(main_file, ancillary_files or [])
        self.publish(main_file, ancillary_files or [])


if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
