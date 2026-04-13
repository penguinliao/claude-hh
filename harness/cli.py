"""CLI entry point — thin wrapper around bin/harness_cli.py main()."""

from __future__ import annotations

import sys
from pathlib import Path

# bin/harness_cli.py lives at ../bin/ relative to this file
_BIN_DIR = str(Path(__file__).resolve().parent.parent / "bin")
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)

from harness_cli import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
