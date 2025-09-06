"""Minimal PyPI publisher stub.

Reduced to a deterministic, no-op publisher that preserves the public
API used by orchestrators. It performs a basic existence check for the
main file and optionally logs when invoked in debug mode.
"""

from __future__ import annotations

import os
from typing import Any, Iterable


class x_cls_make_pypi_x:
    """Very small publisher stub.

    The class intentionally does nothing that has side effects (no builds,
    no uploads, no temp dirs). It keeps the same method signatures so
    callers remain compatible.
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
        """Minimal, deterministic publisher: check main_file then return.

        This function intentionally performs no builds or network uploads.
        """
        if not os.path.exists(main_file):
            raise FileNotFoundError(main_file)

        if self.debug:
            self._log(
                f"publish skipped for {self.name} {self.version} (minimal stub)"
            )

    def publish(self, main_file: str, ancillary_files: Iterable[str]) -> None:
        return self.prepare_and_publish(main_file, ancillary_files)
