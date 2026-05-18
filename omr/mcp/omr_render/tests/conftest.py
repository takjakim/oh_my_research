"""Make the omr_render package importable regardless of pytest rootdir.

Adds omr/mcp/ to sys.path so `import omr_render` resolves the package
directory `omr/mcp/omr_render/` without requiring installation or the `mcp`
package.
"""

import os
import sys

_PKG_PARENT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _PKG_PARENT not in sys.path:
    sys.path.insert(0, _PKG_PARENT)
