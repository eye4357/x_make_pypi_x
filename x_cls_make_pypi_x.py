from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import textwrap


class x_cls_make_pypi_x:
    """
    A helper class to automate the process of preparing and publishing a Python package to PyPI.

    Features:
    - Create all necessary files (LICENSE, README, setup.py, requirements.txt, .pypirc).
    - Automate the build and upload process to TestPyPI then PyPI.
    - Dry run mode to verify file creation and builds without uploading.

    Instructions for Use:
    1. Ensure Python 3.6 or higher is installed on your system.
    2. Install the required dependencies: `pip install build twine`.
        3. Use this class from your own script:
             - Choose whether to perform a dry run or a wet run (via constructor argument).
             - Provide your TestPyPI and PyPI API tokens via environment variables:
                 - TESTPYPI_API_TOKEN
                 - PYPI_API_TOKEN
    4. Verify the generated files in the current working directory:
       - LICENSE
       - README.md
       - setup.py
       - requirements.txt
       - .pypirc (also saved in `%USERPROFILE%\\.pypirc` for wet runs).
    5. For a wet run, the package will be uploaded to TestPyPI and, if successful, to PyPI.

    Manual Steps Before Running:
    - Increment the version number in `setup.py` if this is not the first release.
    - Ensure your Python file contains the necessary package structure and code.
    - Test your package locally to confirm it works as expected.
    - Create accounts on PyPI and TestPyPI if you don't already have them.

    Steps to Create PyPI and TestPyPI Accounts:
    1. Go to the PyPI website: https://pypi.org/account/register/.
    2. Fill in the registration form with your email, username, and password.
    3. Verify your email address by clicking the link sent to your inbox.
    4. Repeat the same process for TestPyPI at https://test.pypi.org/account/register/.
    5. Use the same credentials for both accounts to simplify management.

    Additional Notes:
    - The `.pypirc` file is created in the dist/ folder and `%USERPROFILE%\\.pypirc` (skipped in dry run).
    - Ensure you have an active internet connection for a wet run.
    - If you encounter issues, check the generated files and logs for errors.
    - For more information on packaging, refer to the official Python Packaging Guide: https://packaging.python.org/.

    This tool is designed to simplify the process of publishing Python packages, making it accessible to anyone, even those new to PyPI.
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
        # Class variable to control evidence deletion behavior
        self.cleanup_evidence = cleanup_evidence  # Set to False to skip evidence deletion
        # Class variable to control dry-run behavior (no upload, token prompts skipped)
        self.dry_run = dry_run
        # Resolve API tokens at initialization (skip in dry-run). Tokens are read from env vars.
        if self.dry_run:
            self.pypi_token = ""
            self.testpypi_token = ""
            print("Dry run mode: skipping token prompts and uploads.")
        else:
            # Read tokens from environment variables
            self.testpypi_token = (
                os.environ.get("TESTPYPI_API_TOKEN")
                or os.environ.get("TEST_PYPI_API_TOKEN")
                or os.environ.get("TEST_PYPI_TOKEN")
                or ""
            )
            self.pypi_token = os.environ.get("PYPI_API_TOKEN") or os.environ.get("PYPI_TOKEN") or ""
            if not self.testpypi_token:
                raise ValueError(
                    "Missing TestPyPI token. Set the TESTPYPI_API_TOKEN environment variable before running."
                )
            if not self.pypi_token:
                raise ValueError(
                    "Missing PyPI token. Set the PYPI_API_TOKEN environment variable before running."
                )
            print("API tokens loaded from environment for TestPyPI and PyPI.")

    # Interactive token prompts removed; tokens now come from environment variables.

    @staticmethod
    def dedent_multiline(multiline_string: str) -> str:
        """Dedent a triple-quoted block while preserving relative indentation and blank lines."""
        # Keep pretty indentation in source; remove common leading whitespace for output
        return textwrap.dedent(multiline_string).lstrip("\n").rstrip() + "\n"

    def create_files(self, python_file: str, ancillary_files: list[str]) -> None:
        """Create LICENSE, README, setup.py, requirements.txt, .pypirc, and include ancillary files."""
        project_dir = os.path.dirname(python_file)
        os.chdir(project_dir)

        # Ensure dist directory exists for build artifacts in the same directory as the main Python file
        dist_dir = os.path.join(os.path.dirname(python_file), "dist")
        os.makedirs(dist_dir, exist_ok=True)

        # Create subdirectories for organization
        docs_dir = os.path.join(project_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)

        # LICENSE in docs/
        license_text = self.dedent_multiline(
            """
            MIT License

            Copyright (c) 2025 [Your Name or Organization]

            Permission is hereby granted, free of charge, to any person obtaining a copy
            of this software and associated documentation files (the "Software"), to deal
            in the Software without restriction, including without limitation the rights
            to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
            copies of the Software, and to permit persons to whom the Software is
            furnished to do so, subject to the following conditions:

            The above copyright notice and this permission notice shall be included in all
            copies or substantial portions of the Software.

            THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
            IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
            FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
            AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
            LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
            OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
            SOFTWARE.
            """
        )
        with open(os.path.join(docs_dir, "LICENSE"), "w", encoding="utf-8") as f:
            f.write(license_text)

        # README
        with open(os.path.join(docs_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(f"# {self.name}\n\n{self.dedent_multiline(self.description)}\n")

        # Derive a valid package (module) name from the provided distribution name
        package_name = self.name.replace("-", "_")
        # Package directory and __init__
        package_dir = os.path.join(project_dir, package_name)
        os.makedirs(package_dir, exist_ok=True)
        with open(os.path.join(package_dir, "__init__.py"), "w", encoding="utf-8") as f:
            f.write(f"# This is the __init__.py file for the {package_name} package")

        # Copy main script
        selected_script_name = os.path.basename(python_file)
        destination_script_path = os.path.join(package_dir, selected_script_name)
        shutil.copy2(python_file, destination_script_path)

        # Copy ancillary files preserving relative structure
        # Determine common root for preserving relative structure (fallback for cross-drive paths on Windows)
        if ancillary_files:
            try:
                common_root = os.path.commonpath([python_file, *ancillary_files])
            except ValueError:
                common_root = os.path.dirname(python_file)
        else:
            common_root = os.path.dirname(python_file)
        for ancillary_file in ancillary_files:
            relative_path = os.path.relpath(ancillary_file, common_root)
            destination_path = os.path.join(package_dir, relative_path)
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            shutil.copy2(ancillary_file, destination_path)

        # setup.py content
        setup_content = self.dedent_multiline(
            """
            import os
            from setuptools import setup

            with open(os.path.join("docs", "README.md"), encoding="utf-8") as fh:
                long_desc = fh.read()

            setup(
                name="{dist_name}",
                version="{version}",
                author="{author}",
                author_email="{email}",
                description="{description}",
                long_description=long_desc,
                long_description_content_type="text/markdown",
                url="https://pypi.org/project/{dist_name}/",
                packages=["{package_name}"],
                include_package_data=True,
                package_data={{"{package_name}": ["*", "**/*"]}},
                install_requires={dependencies},
                classifiers=[
                    "Programming Language :: Python :: 3",
                    "License :: OSI Approved :: MIT License",
                    "Operating System :: OS Independent",
                ],
                python_requires=">=3.6",
                zip_safe=False,
            )
            """
        ).format(
            dist_name=self.name,
            version=self.version,
            author=self.author,
            email=self.email,
            description=self.description,
            dependencies=self.dependencies,
            package_name=package_name,
        )
        with open(os.path.join(project_dir, "setup.py"), "w", encoding="utf-8") as f:
            f.write(setup_content)

        # MANIFEST.in
        manifest_lines = [
            f"recursive-include {package_name} *",
            "include docs/README.md",
            "include LICENSE",
        ]
        with open(os.path.join(project_dir, "MANIFEST.in"), "w", encoding="utf-8") as f:
            f.write("\n".join(manifest_lines))

        # Root LICENSE
        root_license_path = os.path.join(project_dir, "LICENSE")
        try:
            with open(root_license_path, "w", encoding="utf-8") as f:
                f.write(self.dedent_multiline(self.license_text) or license_text)
        except Exception:
            pass

        # requirements.txt (for reference)
        with open(os.path.join(dist_dir, "requirements.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(self.dependencies))

        # .pypirc
        self.generate_pypirc(dist_dir)

    def generate_pypirc(self, dist_dir: str) -> None:
        print("Generating .pypirc file...")

        # Validate tokens (skip in dry-run)
        if not self.dry_run:
            if "\n" in self.pypi_token or len(self.pypi_token.split()) > 1:
                raise ValueError(
                    "Invalid PyPI token detected. Ensure the token is a single string and not a list of recovery codes."
                )
            if "\n" in self.testpypi_token or len(self.testpypi_token.split()) > 1:
                raise ValueError(
                    "Invalid TestPyPI token detected. Ensure the token is a single string and not a list of recovery codes."
                )

        # Build content (pretty in source, stripped for output)
        pypirc_content = self.dedent_multiline(
            f"""
            [distutils]
            index-servers =
                testpypi
                pypi

            [testpypi]
            repository = https://test.pypi.org/legacy/
            username = __token__
            password = {self.testpypi_token}

            [pypi]
            repository = https://upload.pypi.org/legacy/
            username = __token__
            password = {self.pypi_token}
            """
        )

        # Do not print full content to avoid leaking API tokens
        print(".pypirc content prepared (tokens not displayed).")

        # Save .pypirc in the dist directory
        dist_pypirc_path = os.path.join(dist_dir, ".pypirc")
        with open(dist_pypirc_path, "w", encoding="utf-8") as f:
            f.write(pypirc_content)
        print(f".pypirc created at: {dist_pypirc_path}")

        # Save .pypirc in the user's home directory (skip in dry-run to avoid overwriting)
        if not self.dry_run:
            home_pypirc_path = os.path.join(os.environ.get("USERPROFILE", ""), ".pypirc")
            if home_pypirc_path:
                with open(home_pypirc_path, "w", encoding="utf-8") as f:
                    f.write(pypirc_content)
                print(f".pypirc also saved at: {home_pypirc_path}")

        # Validate .pypirc format
        try:
            parser = configparser.ConfigParser()
            parser.read_string(pypirc_content)
            print(".pypirc format validated successfully.")
        except configparser.ParsingError as e:
            print("Error validating .pypirc format:", e)
            print("Please check the generated .pypirc file for formatting issues.")
            raise

    def run_subprocess(self, command: str) -> bool:
        """Run a subprocess command and print its output. Returns True on success, False on failure."""
        try:
            result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
            print("Subprocess output:", result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            print("Subprocess failed with error:", e.stderr)
            print("Return code:", e.returncode)
            print("Command:", e.cmd)
            print("Full output:", e.output)
            return False

    def prepare(self, main_python_file: str, ancillary_files: list[str]) -> None:
        """Prepare the environment by validating files and cleaning up."""
        # Check for the existence of the main Python file
        if not os.path.exists(main_python_file):
            raise FileNotFoundError(f"Main Python file '{main_python_file}' does not exist.")

        print(f"Main Python file found: {main_python_file}")

        # Parse all files recursively in the parent directory of the main Python file
        parent_dir = os.path.dirname(main_python_file)
        all_files: list[str] = []
        for root, _, files in os.walk(parent_dir):
            for file in files:
                all_files.append(os.path.normpath(os.path.join(root, file)))

        # Normalize ancillary files
        ancillary_files = [os.path.normpath(file) for file in ancillary_files]

        # Debug: Print normalized files found in the directory structure
        print("Normalized files found in directory structure:", all_files)

        # Ensure every ancillary file is in the directory structure
        for ancillary_file in ancillary_files:
            if ancillary_file not in all_files:
                print(
                    "Expected ancillary file not found:", ancillary_file
                )  # Debug: Log missing file
                raise FileNotFoundError(
                    f"Ancillary file '{ancillary_file}' is not found in the directory structure."
                )

        print("All ancillary files are present in the directory structure.")

        # Define git-critical files/folders to always preserve
        GIT_CRITICAL = {
            ".git",
            ".gitignore",
            ".gitattributes",
            ".github",
            ".pre-commit-config.yaml",
            "pyproject.toml",
        }

        def is_git_critical(path: str) -> bool:
            parts = set(os.path.normpath(path).split(os.sep))
            return any(item in parts for item in GIT_CRITICAL)

        # Delete any file that is not the main Python file, an ancillary file, or git-critical
        for file_path in all_files:
            if (
                file_path != os.path.normpath(main_python_file)
                and file_path not in ancillary_files
                and not is_git_critical(file_path)
            ):
                print(f"Deleting unrelated file: {file_path}")
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")

        # Delete all empty directories except git-critical ones
        for root, dirs, _ in os.walk(parent_dir, topdown=False):
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                if not os.listdir(dir_path) and not is_git_critical(dir_path):
                    print(f"Deleting empty directory: {dir_path}")
                    try:
                        os.rmdir(dir_path)
                    except Exception as e:
                        print(f"Failed to delete directory {dir_path}: {e}")

    def publish(self, main_python_file: str, ancillary_files: list[str]) -> None:
        """Publish the package to PyPI."""
        # Create necessary files
        self.create_files(main_python_file, ancillary_files)

        # Step 1: Install build and (optionally) twine
        if self.dry_run:
            self.run_subprocess("pip install build")
        else:
            self.run_subprocess("pip install build twine")

        # Step 2: Build the package
        # Change to the directory containing setup.py before building
        project_dir = os.path.dirname(main_python_file)
        os.chdir(project_dir)

        # Run the build process
        self.run_subprocess("python -m build")

        # Validate build output and restrict uploads to current version only
        dist_path = os.path.join(project_dir, "dist")
        artifacts = [
            os.path.join(dist_path, f)
            for f in os.listdir(dist_path)
            if f.startswith(f"{self.name}-{self.version}")
            and (f.endswith(".tar.gz") or f.endswith(".whl"))
        ]
        if not artifacts:
            print(
                "Error: No distribution files for the current version found in the dist directory."
            )
            return
        print("Artifacts to upload:", artifacts)

        # Upload to TestPyPI, then PyPI only if TestPyPI succeeds (skip in dry-run)
        if not self.dry_run:
            files = " ".join([f'"{p}"' for p in artifacts])
            test_cmd = f"python -m twine upload --repository testpypi {files} --verbose"
            print(f"Running command: {test_cmd}")
            ok = self.run_subprocess(test_cmd)
            if not ok:
                print("TestPyPI upload failed; skipping PyPI upload.")
                return
            pypi_cmd = f"python -m twine upload --repository pypi {files} --verbose"
            print(f"Running command: {pypi_cmd}")
            self.run_subprocess(pypi_cmd)

    def prepare_and_publish(self, main_python_file: str, ancillary_files: list[str]) -> None:
        """Run the steps to prepare and publish the package to PyPI."""
        if self.cleanup_evidence:
            # Cleanup before publishing
            self.prepare(main_python_file, ancillary_files)

        # Always publish
        self.publish(main_python_file, ancillary_files)

        if self.cleanup_evidence:
            # Cleanup after publishing
            self.prepare(main_python_file, ancillary_files)


if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
else:
    pass
