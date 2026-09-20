# incidents/

Same format as the llms.surf diary (frontmatter `id/titulo/data/recorrivel/regra/status/repo/interage_com`,
sections Sintoma / Causa / Correção aplicada / Pode acontecer de novo?), in Portuguese, so a file
can be copied verbatim into the private diary. Every failure that cost a human a retry becomes an
entry; every recurring entry becomes a mechanism in `stages/lint.py`, the orchestrator tests, or
the specs' oracles.
