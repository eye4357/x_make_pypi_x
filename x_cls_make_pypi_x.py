from __future__ import annotations
import os
import shutil
import textwrap
import sys
import stat
import tempfile

'''red rabbit 2025_0902_0944'''


class x_cls_make_pypi_x:
    def version_exists_on_pypi(self) -> bool:
        """Check if the current package name and version already exist on PyPI."""
        import urllib.request, json
        url = f"https://pypi.org/pypi/{self.name}/json"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.load(response)
            return self.version in data.get("releases", {})
        except Exception as e:
            print(f"WARNING: Could not check PyPI for {self.name}=={self.version}: {e}")
            return False
    """
    Minimal PyPI publisher: Only copies the main file, ancillary files, and preserves CI files. No legacy packaging files are created or required.
    """
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

    def update_pyproject_toml(self, project_dir: str) -> None:
        """Update pyproject.toml with the correct name and version before building. Print and validate after update."""
        pyproject_path = os.path.join(project_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            print(f"No pyproject.toml found in {project_dir}, skipping update.")
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
        # If no [project] section, add it
        if not project_section_found:
            new_lines.append("\n[project]\n")
            new_lines.append(f'name = "{self.name}"\n')
            new_lines.append(f'version = "{self.version}"\n')
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Updated pyproject.toml with name={self.name}, version={self.version}")
        # Print and validate pyproject.toml
        with open(pyproject_path, "r", encoding="utf-8") as f:
            contents = f.read()
        print("pyproject.toml after update:")
        print(contents)
        # Validate [project] section
        import re
        name_match = re.search(r'^name\s*=\s*"(.+)"', contents, re.MULTILINE)
        version_match = re.search(r'^version\s*=\s*"(.+)"', contents, re.MULTILINE)
        if not name_match or not name_match.group(1).strip():
            raise RuntimeError("pyproject.toml missing or empty 'name' in [project] section after update.")
        if not version_match or not version_match.group(1).strip():
            raise RuntimeError("pyproject.toml missing or empty 'version' in [project] section after update.")

    def create_files(self, main_file: str, ancillary_files: list[str]) -> None:
        """
        Create a minimal package directory named after the package, copy the explicit main file and ancillary files, and ensure __init__.py exists.
        """
        import tempfile, stat, traceback, time
        package_name = self.name
        # Use a custom build directory inside the repo for diagnostics
        repo_build_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "_build_temp_x_pypi_x"))
        if not os.path.exists(repo_build_root):
            os.makedirs(repo_build_root, exist_ok=True)
        import uuid
        build_dir = os.path.join(repo_build_root, f"_build_{package_name}_{uuid.uuid4().hex}")
        os.makedirs(build_dir, exist_ok=True)
        package_dir = os.path.join(build_dir, package_name)

        def print_stat_info(path: str):
            print(f"STAT: {path}")
            print(f"  Exists: {os.path.lexists(path)}")
            print(f"  Symlink: {os.path.islink(path)}")
            print(f"  File: {os.path.isfile(path)}")
            print(f"  Dir: {os.path.isdir(path)}")
            try:
                print(f"  Stat: {os.stat(path)}")
            except Exception as e:
                print(f"  Stat failed: {e}")

        def force_remove_any(path: str) -> None:
            """Remove any file, symlink, or folder at path, with verbose stat diagnostics."""
            print(f"Attempting to remove: {path}")
            print_stat_info(path)
            try:
                if os.path.islink(path):
                    os.unlink(path)
                elif os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, onexc=lambda func, p, exc_info: os.chmod(p, stat.S_IWRITE) or func(p))
            except Exception as e:
                print(f"ERROR: Could not forcibly remove {path}: {e}")
                traceback.print_exc()
            print(f"After removal attempt:")
            print_stat_info(path)

        # Remove and verify both build_dir and package_dir
        for path in [package_dir, build_dir]:
            if os.path.lexists(path):
                force_remove_any(path)
                if os.path.lexists(path):
                    print(f"FATAL: {path} still exists after attempted removal. Aborting.")
                    raise RuntimeError(f"Could not remove: {path}")

        # Recreate build dir
        os.makedirs(build_dir, exist_ok=True)

        # Remove any file, folder, or symlink named package_dir before creation
        if os.path.lexists(package_dir):
            print(f"DIAGNOSTIC: {package_dir} exists before creation.")
            print_stat_info(package_dir)
            force_remove_any(package_dir)
            time.sleep(1)
            if os.path.lexists(package_dir):
                print(f"WARNING: {package_dir} still exists after first forced removal and delay.")
                print_stat_info(package_dir)
                print(f"Attempting final forced removal and longer delay...")
                force_remove_any(package_dir)
                time.sleep(2)
                if os.path.lexists(package_dir):
                    print(f"FATAL: {package_dir} still exists after final forced removal and delay.")
                    print_stat_info(package_dir)
                    print(f"Contents of parent build directory:")
                    for item in os.listdir(build_dir):
                        print(f" - {item}")
                    raise RuntimeError(f"Could not remove package_dir: {package_dir}")

        # Create the package dir only if it does not exist
        print(f"DIAGNOSTIC: About to create {package_dir} if needed.")
        print_stat_info(package_dir)
        if not os.path.exists(package_dir):
            try:
                os.makedirs(package_dir, exist_ok=True)
            except OSError as e:
                print(f"FATAL: Could not create {package_dir}: {e}")
                print_stat_info(package_dir)
                if os.path.lexists(package_dir):
                    print(f"Contents of parent build directory:")
                    for item in os.listdir(build_dir):
                        print(f" - {item}")
                raise
        else:
            print(f"INFO: {package_dir} already exists as a directory, proceeding.")

        # After ancillary file copying, ensure only a directory exists at package_dir
        print(f"DIAGNOSTIC: After ancillary file copy, checking {package_dir}.")
        print_stat_info(package_dir)
        if os.path.lexists(package_dir) and not os.path.isdir(package_dir):
            print(f"WARNING: {package_dir} is not a directory after ancillary file copy. Forcing removal.")
            force_remove_any(package_dir)
            time.sleep(1)
            if os.path.lexists(package_dir):
                print(f"FATAL: {package_dir} still exists after forced removal post ancillary copy.")
                print_stat_info(package_dir)
                raise RuntimeError(f"Could not ensure package_dir is a directory: {package_dir}")

        # Copy main file as <package>/<main_file>
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
                # Remove destination if it exists to avoid copytree error
                if os.path.lexists(dest):
                    print(f"DIAGNOSTIC: Ancillary destination {dest} exists before copy. Removing...")
                    print_stat_info(dest)
                    force_remove_any(dest)
                    time.sleep(0.5)
                shutil.copytree(ancillary_path, dest)
            elif os.path.isfile(ancillary_path):
                shutil.copy2(ancillary_path, os.path.join(package_dir, os.path.basename(ancillary_path)))
        # Set project_dir for build/publish
        self._project_dir = build_dir

        # Ensure pyproject.toml exists in build_dir
        pyproject_path = os.path.join(build_dir, "pyproject.toml")
        if not os.path.exists(pyproject_path):
            # Use SPDX identifier (e.g., "MIT") for license field
            spdx_license = "MIT" if "MIT" in self.license_text else self.license_text.splitlines()[0] if self.license_text else ""
            pyproject_content = (
                f"[project]\n"
                f"name = \"{self.name}\"\n"
                f"version = \"{self.version}\"\n"
                f"description = \"{self.description}\"\n"
                f"authors = [{{name = \"{self.author}\", email = \"{self.email}\"}}]\n"
                f"license = \"{spdx_license}\"\n"
                f"dependencies = {self.dependencies if self.dependencies else []}\n"
            )
            with open(pyproject_path, "w", encoding="utf-8") as f:
                f.write(pyproject_content)

            # Optionally, write full license text to LICENSE file in package_dir
            if self.license_text:
                license_file_path = os.path.join(package_dir, "LICENSE")
                with open(license_file_path, "w", encoding="utf-8") as lf:
                    lf.write(self.license_text)

    def prepare(self, main_file: str, ancillary_files: list[str]) -> None:
        if not os.path.exists(main_file):
            raise FileNotFoundError(f"Main file '{main_file}' does not exist.")
        print(f"Main file found: {main_file}")
        for ancillary_file in ancillary_files:
            if not os.path.exists(ancillary_file):
                print(f"Expected ancillary file not found: {ancillary_file}")
                raise FileNotFoundError(f"Ancillary file '{ancillary_file}' is not found.")
        print("All ancillary files are present.")

    def publish(self, main_file: str, ancillary_files: list[str]) -> None:
        # Check if version already exists on PyPI
        if self.version_exists_on_pypi():
            print(f"SKIP: {self.name} version {self.version} already exists on PyPI. Skipping publish.")
            return
        self.create_files(main_file, ancillary_files)
        print("Main and ancillary files copied. Updating pyproject.toml...")
        project_dir = self._project_dir
        self.update_pyproject_toml(project_dir)
        os.chdir(project_dir)
        # Clean dist/ before build
        dist_dir = os.path.join(project_dir, "dist")
        if os.path.exists(dist_dir):
            print("Cleaning dist/ directory before build...")
            for f in os.listdir(dist_dir):
                try:
                    os.remove(os.path.join(dist_dir, f))
                except Exception as e:
                    print(f"Could not remove {f}: {e}")
        build_cmd = f"{sys.executable} -m build"
        print(f"Running build: {build_cmd}")
        build_result = os.system(build_cmd)
        if build_result != 0:
            print("Build failed.")
            raise RuntimeError("Build failed. Aborting publish.")
        if not os.path.exists(dist_dir):
            print("dist/ directory not found after build.")
            raise RuntimeError("dist/ directory not found. Aborting publish.")
        # Only upload files matching package name and version
        valid_prefixes = [f"{self.name}-{self.version}"]
        files = [
            os.path.join(dist_dir, f)
            for f in os.listdir(dist_dir)
            if any(f.startswith(prefix) for prefix in valid_prefixes) and f.endswith((".tar.gz", ".whl"))
        ]
        if not files:
            print("No valid distribution files found for upload.")
            raise RuntimeError("No valid distribution files found. Aborting publish.")
        files_str = ' '.join([f'"{f}"' for f in files])
        # Check for .pypirc or TWINE_USERNAME/TWINE_PASSWORD/TWINE_API_TOKEN
        pypirc_path = os.path.expanduser("~/.pypirc")
        has_pypirc = os.path.exists(pypirc_path)
        has_env_creds = any([
            os.environ.get("TWINE_USERNAME"),
            os.environ.get("TWINE_PASSWORD"),
            os.environ.get("TWINE_API_TOKEN"),
        ])
        if not has_pypirc and not has_env_creds:
            print("WARNING: No PyPI credentials found (.pypirc or TWINE env vars). Upload will likely fail.")
        twine_cmd = f"{sys.executable} -m twine upload {files_str} --verbose"
        print(f"Running upload: {twine_cmd}")
        # Use subprocess to capture output
        import subprocess
        try:
            result = subprocess.run(twine_cmd, shell=True, capture_output=True, text=True)
            print("Twine stdout:")
            print(result.stdout)
            print("Twine stderr:")
            print(result.stderr)
            if result.returncode != 0:
                print(f"Upload to PyPI failed with exit code {result.returncode}.")
                raise RuntimeError(f"Twine upload failed. See output above.")
            else:
                print("Upload to PyPI succeeded.")
        except Exception as e:
            print(f"Exception during Twine upload: {e}")
            raise

    def prepare_and_publish(self, main_file: str, ancillary_files: list[str]) -> None:
        if self.cleanup_evidence:
            self.prepare(main_file, ancillary_files)
        self.publish(main_file, ancillary_files)
        if self.cleanup_evidence:
            self.prepare(main_file, ancillary_files)

if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
