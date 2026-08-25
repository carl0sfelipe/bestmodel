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
