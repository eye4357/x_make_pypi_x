# x_make_pypi_x — Lab Notes from Walter White

> "Every release leaves evidence. This rig makes sure the packages we drop on PyPI look clean, typed, and bulletproof."

## Manifesto
x_make_pypi_x is the publishing arm of the lab. It snapshots a package module, injects type metadata, builds wheels and source tarballs with `python -m build`, and drives `twine upload` with the right safeguards—`--skip-existing`, credential checks, and output logging. When the orchestrator says ship, this module ensures the drop is staged, sealed, and tracked in the Road to 0.20.0 ledger.

### Highlights
- Replicates the target module into an isolated build workspace before packaging.
- Generates `py.typed`, `.pyi` stubs, and `MANIFEST.in` entries so downstream consumers get full typing signals.
- Guards against duplicate releases by probing PyPI JSON metadata before uploading.
- Surfaces build and upload diagnostics through the orchestrator logger and stdout, even when running headless.

## Ingredients
- Python 3.11+
- `build` and `twine` installed in the active virtual environment
- Optional QA stack: Ruff, Black, MyPy, Pyright, and pytest to vet local helpers before publishing
- PyPI credentials via `.pypirc` or `TWINE_*` environment variables (`TWINE_API_TOKEN`, `TWINE_USERNAME`, `TWINE_PASSWORD`)

## Cook Instructions
1. `python -m venv .venv`
2. `.\.venv\Scripts\Activate.ps1`
3. `python -m pip install --upgrade pip`
4. `pip install build twine`
5. Export credentials if you are not using `.pypirc`:
   - `$env:TWINE_API_TOKEN = "pypi-your-token"`
6. Drive publishing from the orchestrator or a focused script. For a quick standalone run, drop this into `publish_driver.py` and execute `python publish_driver.py`:
   ```python
   from x_cls_make_pypi_x import XClsMakePypiX

   publisher = XClsMakePypiX(
       name="your_package",
       version="0.1.0",
       author="Walter White",
       email="heisenberg@example.com",
       description="Blueprint for a PyPI release",
       license_text="MIT",
       dependencies=["requests"],
       ctx=None,
   )
   publisher.prepare_and_publish(
       main_file="src/your_package/__init__.py",
       ancillary_files=["README.md", "pyproject.toml"],
   )
   ```

## Quality Assurance
| Check | Command |
| --- | --- |
| Formatting sweep | `python -m black .`
| Lint interrogation | `python -m ruff check .`
| Type audit | `python -m mypy x_cls_make_pypi_x.py`
| Static contract scan | `python -m pyright`
| Functional verification | `pytest` *(if you wire local tests for your package)*

## Distribution Chain
- [Changelog](./CHANGELOG.md)
- [Road to 0.20.0 Control Room](../x_0_make_all_x/Change%20Control/0.20.0/index.md)
- [Road to 0.20.0 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.0/Road%20to%200.20.0%20Engineering%20Proposal%20-%20Walter%20White.md)

## Lab Etiquette
Stage every publish run in a clean workspace, document the package intent in Change Control, and capture the exact artifact hashes in your release notes. If PyPI declines a drop, fix the evidence trail before you try again.
