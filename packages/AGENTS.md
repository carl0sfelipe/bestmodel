# packages/ — Map

Shared Python libraries (flat-module layout exposed via root pytest `pythonpath`;
each has a declarative pyproject but is NOT pip-installed — see decision D4 in
(internal decision log). Dependency direction: apps → packages; packages never import apps.

| Package | Purpose | Map |
|---|---|---|
| `domain-schema/` | Pydantic models + report contract 0.9.0 | `domain-schema/AGENTS.md` |
| `roofline-kernel/` | VRAM/context + decode/prefill predictors | `roofline-kernel/AGENTS.md` |
| `runtime-probes/` | Probe protocol + engine stdout parsers | `runtime-probes/AGENTS.md` |
| `recommendation-engine/` | ranking score + feasibility filter | `recommendation-engine/AGENTS.md` |
| `fake-adapters/` | test doubles for API providers | `fake-adapters/AGENTS.md` |

Conventions: one concept per module; functions 4–20 lines, files < 500 lines;
no vague names (`data`, `handler`, `Manager`); exceptions carry the offending
value; tests live in `<pkg>/tests/` and run via root `make test`.
