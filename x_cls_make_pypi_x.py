from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import textwrap


class x_cls_make_pypi_x:
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
    # No token logic needed; publishing is now manual/CI only.

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
        if os.path.abspath(python_file) != os.path.abspath(destination_script_path):
            shutil.copy2(python_file, destination_script_path)

        # Copy ancillary files
        for ancillary_file in ancillary_files:
            destination_path = os.path.join(project_dir, os.path.basename(ancillary_file))
            if os.path.abspath(ancillary_file) != os.path.abspath(destination_path):
                shutil.copy2(ancillary_file, destination_path)

    # .pypirc generation removed; publishing is now manual/CI only.

    # Subprocess logic removed; no build or upload commands are run.

    def prepare(self, main_python_file: str, ancillary_files: list[str]) -> None:
        """Prepare the environment by validating files only."""
        # Check for the existence of the main Python file
        if not os.path.exists(main_python_file):
            raise FileNotFoundError(f"Main Python file '{main_python_file}' does not exist.")

        print(f"Main Python file found: {main_python_file}")

        # Ensure every ancillary file exists
        for ancillary_file in ancillary_files:
            if not os.path.exists(ancillary_file):
                print(f"Expected ancillary file not found: {ancillary_file}")
                raise FileNotFoundError(f"Ancillary file '{ancillary_file}' is not found.")

        print("All ancillary files are present.")

    def publish(self, main_python_file: str, ancillary_files: list[str]) -> None:
        """Publish step: Only copies files, no build or upload."""
        self.create_files(main_python_file, ancillary_files)
        print("Main and ancillary files copied. No packaging or publishing performed.")

    def prepare_and_publish(self, main_python_file: str, ancillary_files: list[str]) -> None:
        """Run the steps to prepare and publish the package: only copies files."""
        if self.cleanup_evidence:
            self.prepare(main_python_file, ancillary_files)
        self.publish(main_python_file, ancillary_files)
        if self.cleanup_evidence:
            self.prepare(main_python_file, ancillary_files)


if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
else:
    pass
