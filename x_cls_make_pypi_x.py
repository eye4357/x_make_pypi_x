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
        self.cleanup_evidence = cleanup_evidence
        self.dry_run = dry_run
        # Token loading logic from registry/user env
        def _mask(token: str | None, head: int = 6, tail: int = 4) -> str:
            if not token:
                return ""
            t = str(token)
            if len(t) <= head + tail:
                return "*" * len(t)
            return f"{t[:head]}...{t[-tail:]}"

        def _get_user_env(var: str) -> str | None:
            try:
                import winreg
            except Exception:
                return None
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                    val, _ = winreg.QueryValueEx(key, var)
                    if isinstance(val, str) and val:
                        return val
                    return None
            except Exception:
                return None

        def _ensure(keys: list[str]) -> str | None:
            for k in keys:
                v = os.environ.get(k)
                if v:
                    return v
            primary = keys[0]
            v = _get_user_env(primary)
            if v:
                os.environ[primary] = v
                return v
            return None

        if self.dry_run:
            self.pypi_token = ""
            self.testpypi_token = ""
            print("Dry run mode: skipping token prompts and uploads.")
        else:
            test_key_candidates = ["TESTPYPI_API_TOKEN", "TEST_PYPI_API_TOKEN", "TEST_PYPI_TOKEN"]
            pypi_key_candidates = ["PYPI_API_TOKEN", "PYPI_TOKEN"]
            self.testpypi_token = _ensure(test_key_candidates) or ""
            self.pypi_token = _ensure(pypi_key_candidates) or ""
            print(f"Env tokens - TESTPYPI: {'set' if self.testpypi_token else 'missing'} {_mask(self.testpypi_token)} | PYPI: {'set' if self.pypi_token else 'missing'} {_mask(self.pypi_token)}")
            if not self.testpypi_token:
                raise ValueError("Missing TestPyPI token. Set the TESTPYPI_API_TOKEN environment variable before running.")
            if not self.pypi_token:
                raise ValueError("Missing PyPI token. Set the PYPI_API_TOKEN environment variable before running.")

    # Interactive token prompts removed; tokens now come from environment variables.

    @staticmethod
    def dedent_multiline(multiline_string: str) -> str:
        """Dedent a triple-quoted block while preserving relative indentation and blank lines."""
        # Keep pretty indentation in source; remove common leading whitespace for output
        return textwrap.dedent(multiline_string).lstrip("\n").rstrip() + "\n"

    def create_files(self, python_file: str, ancillary_files: list[str]) -> None:
        """Copy main code and ancillary files only."""
        project_dir = os.path.dirname(python_file)
        os.chdir(project_dir)

        # Copy main script
        selected_script_name = os.path.basename(python_file)
        destination_script_path = os.path.join(project_dir, selected_script_name)
        shutil.copy2(python_file, destination_script_path)

        # Copy ancillary files
        for ancillary_file in ancillary_files:
            destination_path = os.path.join(project_dir, os.path.basename(ancillary_file))
            shutil.copy2(ancillary_file, destination_path)

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

    # Deletion logic removed: this function no longer deletes any files or directories.

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
