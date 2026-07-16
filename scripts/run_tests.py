from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"


def main() -> int:
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret")

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    suite = unittest.defaultTestLoader.discover(str(TESTS_DIR))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
