"""Minimal PyPI publisher stub (pre-commit config references removed).

This lightweight stub provides the small surface area used by other
orchestrator scripts. It intentionally avoids writing or installing
".pre-commit-config.yaml" and is tolerant of build/upload failures.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Iterable


class x_cls_make_pypi_x:
    """Very small publisher stub used during refactor.

    Methods are intentionally best-effort and non-fatal so importing
    this module does not break other scripts while pre-commit behavior
    is being removed.
    """

    def __init__(self, name: str, version: str, **kwargs: Any) -> None:
        self.name = name
        self.version = version
        self.debug = bool(kwargs.get("debug", False))

    def _log(self, *args: Any) -> None:
        if self.debug:
            try:
                print(" ".join(str(a) for a in args))
            except Exception:
                pass

    def prepare_and_publish(
        self, main_file: str, ancillary_files: Iterable[str]
    ) -> None:
        """Create a minimal build dir, try to build and upload, but don't fail hard.

        This stub does not write .pre-commit-config.yaml or install hooks.
        """
        if not os.path.exists(main_file):
            raise FileNotFoundError(main_file)

        build_dir = os.path.abspath(
            os.path.join(
                tempfile.gettempdir(), f"_build_{self.name}_{uuid.uuid4().hex}"
            )
        )
        os.makedirs(build_dir, exist_ok=True)

        try:
            shutil.copy2(
                main_file, os.path.join(build_dir, os.path.basename(main_file))
            )
        except Exception:
            # best-effort copy
            pass

        try:
            subprocess.run(
                [sys.executable, "-m", "build", "--sdist", "--wheel"],
                check=True,
            )
        except Exception:
            self._log("Build step skipped or failed; continuing.")

        try:
            subprocess.run(
                [sys.executable, "-m", "twine", "upload", "dist/*"], check=True
            )
        except Exception:
            self._log(
                "Twine upload skipped or failed (non-fatal for this stub)."
            )

    def publish(self, main_file: str, ancillary_files: Iterable[str]) -> None:
        return self.prepare_and_publish(main_file, ancillary_files)
