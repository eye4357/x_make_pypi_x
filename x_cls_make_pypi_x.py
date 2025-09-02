from __future__ import annotations
import os
import shutil
import textwrap
import sys

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

    def update_pyproject_toml(self, project_dir: str) -> None:
        """Update pyproject.toml with the correct name and version before building."""
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

    def create_files(self, python_file: str, ancillary_files: list[str]) -> None:
        """Copy main code and ancillary files only. If ancillary is a folder, copy recursively."""
        project_dir = os.path.dirname(python_file)
        os.chdir(project_dir)
        selected_script_name = os.path.basename(python_file)
        destination_script_path = os.path.join(project_dir, selected_script_name)
        if os.path.abspath(python_file) != os.path.abspath(destination_script_path):
            shutil.copy2(python_file, destination_script_path)
        for ancillary_path in ancillary_files:
            if os.path.isdir(ancillary_path):
                for root, _, files in os.walk(ancillary_path):
                    rel_root = os.path.relpath(root, os.path.dirname(ancillary_path))
                    dest_root = os.path.join(project_dir, os.path.basename(ancillary_path), rel_root)
                    os.makedirs(dest_root, exist_ok=True)
                    for file in files:
                        src_file = os.path.join(root, file)
                        dest_file = os.path.join(dest_root, file)
                        if os.path.abspath(src_file) != os.path.abspath(dest_file):
                            shutil.copy2(src_file, dest_file)
            elif os.path.isfile(ancillary_path):
                destination_path = os.path.join(project_dir, os.path.basename(ancillary_path))
                if os.path.abspath(ancillary_path) != os.path.abspath(destination_path):
                    shutil.copy2(ancillary_path, destination_path)

    def prepare(self, main_python_file: str, ancillary_files: list[str]) -> None:
        if not os.path.exists(main_python_file):
            raise FileNotFoundError(f"Main Python file '{main_python_file}' does not exist.")
        print(f"Main Python file found: {main_python_file}")
        for ancillary_file in ancillary_files:
            if not os.path.exists(ancillary_file):
                print(f"Expected ancillary file not found: {ancillary_file}")
                raise FileNotFoundError(f"Ancillary file '{ancillary_file}' is not found.")
        print("All ancillary files are present.")

    def publish(self, main_python_file: str, ancillary_files: list[str]) -> None:
        self.create_files(main_python_file, ancillary_files)
        print("Main and ancillary files copied. Updating pyproject.toml...")
        project_dir = os.path.dirname(main_python_file)
        self.update_pyproject_toml(project_dir)
        os.chdir(project_dir)
        build_cmd = f"{sys.executable} -m build"
        print(f"Running build: {build_cmd}")
        build_result = os.system(build_cmd)
        if build_result != 0:
            print("Build failed.")
            return
        dist_dir = os.path.join(project_dir, "dist")
        if not os.path.exists(dist_dir):
            print("dist/ directory not found after build.")
            return
        files = [os.path.join(dist_dir, f) for f in os.listdir(dist_dir) if f.endswith((".tar.gz", ".whl"))]
        if not files:
            print("No distribution files found for upload.")
            return
        files_str = ' '.join([f'"{f}"' for f in files])
        twine_cmd = f"{sys.executable} -m twine upload {files_str} --verbose"
        print(f"Running upload: {twine_cmd}")
        upload_result = os.system(twine_cmd)
        if upload_result != 0:
            print("Upload to PyPI failed.")
        else:
            print("Upload to PyPI succeeded.")

    def prepare_and_publish(self, main_python_file: str, ancillary_files: list[str]) -> None:
        if self.cleanup_evidence:
            self.prepare(main_python_file, ancillary_files)
        self.publish(main_python_file, ancillary_files)
        if self.cleanup_evidence:
            self.prepare(main_python_file, ancillary_files)

if __name__ == "__main__":
    raise SystemExit("This file is not meant to be run directly.")
