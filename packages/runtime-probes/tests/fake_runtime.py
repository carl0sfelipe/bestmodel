"""Fake runtime used by tests: injects fixture stdout without launching the
real llama-cli/ollama binaries."""

import pathlib
from types import SimpleNamespace

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Read a fixture file from ``tests/fixtures``."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class FakeRuntime:
    """Callable stand-in for ``subprocess.run`` that returns fixture stdout."""

    def __init__(self, stdout: str, *, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode

    def __call__(self, _command, **kwargs):
        return SimpleNamespace(
            stdout=self.stdout,
            stderr="",
            returncode=self.returncode,
        )


def fake_runner(stdout: str, *, returncode: int = 0):
    """Return a plain function runner wrapping the given stdout."""

    def run(_command, **kwargs):
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    return run
