# packages/fake-adapters — Map

Test doubles for the public-api provider interfaces (plan §14 decision 13).
Used by apps/public-api tests and the root integration suite; never in prod code.

| Module | Replaces |
|---|---|
| `fake_database.py` | `DatabaseSession` (Postgres). Pre-loads infra/seed catalogs; two seeded validated runs; `add_leaderboard_entry()` helper |
| `fake_artifact_vault.py` | `ArtifactVault` (in-memory bytes) |
| `fake_redis_queue.py` | `BenchmarkQueue` (captures published events for assertions) |

Contract obligation: keep method signatures identical to
`apps/public-api/src/dependencies/database_session_provider.py` — when a method
is added there, add it here in the same commit or tests break loudly (good).

## Change checklist

- Método novo no ABC `DatabaseSession` ⇒ implementar aqui NA MESMA commit;
  `tests/test_session_contract.py` fica vermelho nomeando o que faltar
  (classe U4: interface portada sem corpos).
- Mudou o shape de record (`domain-schema run_record.py`)? O fake valida
  `insert_scenario`/`insert_benchmark_run` contra o modelo — não edite nada
  aqui além de manter o import; se o fake aceitar um record que o Postgres
  rejeita (ou vice-versa), o bug é AQUI ou no modelo, nunca no teste.
- Mudou `infra/seed/*.json`? O fake pré-carrega os mesmos JSONs — nada a
  duplicar. Exceção conhecida: a linha `recipe` é hardcoded aqui E no
  migration 0011; mexer na recipe = atualizar os dois.
- `fetch_leaderboard_entries` do fake é uma lista enlatada
  (`add_leaderboard_entry`), NÃO deriva das runs — divergência consciente
  (registrada na spec S25); derivar é trabalho do S26, não de um fix casual.
