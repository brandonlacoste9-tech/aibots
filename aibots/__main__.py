"""Entry point for ``python -m aibots``."""
from __future__ import annotations

import sys

from aibots.cli import main

if __name__ == "__main__":
    sys.exit(main())
