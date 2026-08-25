"""Public API application package.

Bootstraps the import environment so the application runs outside pytest: the
sibling package source roots are added to ``sys.path`` so the flat domain and
kernel modules resolve when the app is launched directly with uvicorn.
"""

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]

_PACKAGE_SOURCE_ROOTS = (
    _REPO_ROOT / "packages" / "domain-schema" / "src",
    _REPO_ROOT / "packages" / "roofline-kernel" / "src",
    _REPO_ROOT / "packages" / "runtime-probes" / "src",
    _REPO_ROOT / "packages" / "recommendation-engine" / "src",
)

for _root in _PACKAGE_SOURCE_ROOTS:
    _entry = str(_root)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)
