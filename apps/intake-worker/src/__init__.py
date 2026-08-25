"""intake-worker source package.

Bootstraps sys.path for the flat domain and kernel modules so the worker can
be launched directly (``python -m src.worker``) outside pytest.
"""

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[3]

for _entry in (
    _REPO_ROOT / "packages" / "domain-schema" / "src",
    _REPO_ROOT / "packages" / "roofline-kernel" / "src",
):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))
