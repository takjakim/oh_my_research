"""Ensure the omr_scholar package is importable when tests run from repo
root or from inside the package directory, without requiring install."""

import os
import sys

# .../omr/mcp/omr_scholar/tests/conftest.py -> add .../omr/mcp to sys.path
_PKG_PARENT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)
