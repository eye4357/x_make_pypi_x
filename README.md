# x_make_pypi_x — Control Room Lab Notes

> "Every release leaves evidence. This rig makes sure the packages we drop on PyPI look clean, typed, and bulletproof."

## Manifesto
x_make_pypi_x is the publishing arm of the lab. It snapshots a package module, injects type metadata, builds wheels and source tarballs with `python -m build`, and drives `twine upload` with the right safeguards—`--skip-existing`, credential checks, and output logging. When the orchestrator says ship, this module ensures the drop is staged, sealed, and tracked in the Road to 0.20.4 ledger.

## 0.20.4 Command Sequence
Version 0.20.4 pushes publishing telemetry straight into the Release Assembly column. Artifact manifests now land in `make_all_summary.json` with deterministic paths and checksum evidence so the Kanban board shows the exact wheel and sdist that left the lab.

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
        author="Control Room Ops",
        email="lab.ops@example.com",
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
- [Road to 0.20.4 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.4/Road%20to%200.20.4%20Engineering%20Proposal.md)
- [Road to 0.20.3 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.3/Road%20to%200.20.3%20Engineering%20Proposal.md)

## Reconstitution Drill
On the monthly rebuild, reinstall build and twine, execute a dry-run publish against TestPyPI (or mocked credentials), and ensure the artifact manifest still wires into the orchestrator summary. Record tool versions, upload timings, and any authentication hurdles so this README and the Change Control dossier stay precise.

## Lab Etiquette
Stage every publish run in a clean workspace, document the package intent in Change Control, and capture the exact artifact hashes in your release notes. If PyPI declines a drop, fix the evidence trail before you try again.

## Sole Architect Profile
- I am the sole architect for this publisher. Every build workspace, stub generator, credential guard, and logging hook is authored and maintained by me.
- Years of release engineering and packaging work let me orchestrate artifact creation, verification, and compliance without outsourcing a single decision.

## Legacy Workforce Costing
- Traditional model: 1 staff-level release engineer, 1 packaging specialist, 1 security/compliance analyst, and 1 technical writer to document release protocols.
- Timeline: 13-15 engineer-weeks to reproduce the isolated build workspace, stub emitters, and orchestrator telemetry without LLM augmentation.
- Budget range: USD 110k–140k for initial parity, plus continuing costs for credential rotations and compliance audits.

## Techniques and Proficiencies
- Expert in Python packaging, TestPyPI/PyPI workflows, artifact signing, and evidence-driven release management.
- Capable of running entire release programs solo—from requirements through automation, documentation, and operational playbooks.
- Deep familiarity with bridging secure credential flows, type hint packaging, and investor-grade reporting in a single pipeline.

## Stack Cartography
- Language & Tooling: Python 3.11+, `build`, `twine`, `importlib.metadata`, pathlib-based workspace management.
- Security Surface: `.pypirc` integration, `TWINE_*` environment controls, JSON manifest outputs for Change Control.
- Quality Net: Ruff, Black, MyPy, Pyright, optional pytest harnesses for package validation.
- Integrations: Orchestrator stage in `x_0_make_all_x`, dependency alignment with `x_make_pip_updates_x`, logging infrastructure from `x_make_common_x`.
