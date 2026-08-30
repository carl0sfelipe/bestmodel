# S23 — per-user signing keys (assinatura atribuída a usuário)

Status: implementação autorizada pelo dono (2026-08-30). Sequência do
backlog: S25 mergeada (6800cad) → **S23 (esta)** → S24 → L01.

## Por quê (mecânico, não aspiracional)

Hoje TODA submissão é verificada contra UMA chave global
(`TRUSTED_ED25519_PUBLIC_KEY_PATH`, `_verify_signature` em
`submit_benchmark_run.py`): a assinatura prova autenticidade do CLIENTE,
não autoria de USUÁRIO. Sem atribuição criptográfica por usuário,
"capacidade de contribuição" (o cálculo de tier da whitelist do llms-surf)
não é mensurável — é a ponte entre os dois produtos.

## Entregas

1. Migration `0013_signing_keys.sql`: tabela `signing_key` (id, app_user_id,
   label, public_key_pem, algorithm, created_at, revoked_at) + coluna
   NULLABLE `signature_key_id` em `benchmark_run` (princípio D2: opt-in —
   submissões legadas da chave global continuam válidas).
2. `run_record.py`: `signature_key_id: str | None` no `BenchmarkRunRecord`
   + `SigningKeyRecord` (validação do fake). Lockstep do checklist do
   domain-schema: migration + INSERTs Postgres + FakeDatabase + round-trip
   na MESMA commit.
3. ABC (4 métodos, dois backends): `insert_signing_key`,
   `fetch_signing_key_by_id`, `fetch_signing_keys_by_user`,
   `revoke_signing_key`.
4. API (bearer): `POST /v1/auth/signing-keys` (registra PEM ed25519 público,
   rejeita tipo errado), `GET` (lista as minhas, com run_count),
   `DELETE /{id}` (revoga).
5. Submit: `signature_key_id` opcional no form → verifica contra a chave DO
   PRÓPRIO USUÁRIO (chave de outro → 403; revogada → 400; assinatura
   inválida → 400); grava `signature_key_id` na run. Sem o campo → caminho
   legado da chave global, inalterado (CLI Rust e gate não tocam nisto —
   wiring do CLI é follow-up registrado).
6. Rust CLI: FORA do escopo desta story (follow-up).

## Regras

Nao invente numero, prazo, campo ou fonte alem dos listados — todo caminho
citado foi verificado no disco. NUNCA use declare const como workaround.

## Dados verificados

- Existe `apps/public-api/src/services/submit_benchmark_run.py` (chave
  global em `_verify_signature`).
- Existe `apps/public-api/src/routes/auth_route.py` (padrão bearer/token).
- Existe `packages/domain-schema/src/run_record.py` (fonte única do shape).
- Existe `packages/fake-adapters/src/fake_database.py` (valida via
  BenchmarkRunRecord).
- Existe `tests/test_session_video_roundtrip.py` (padrão two-backend).
- Existe `infra/migrations/0012_contributor_reported.sql` (última migration).

## Verificação

Round-trip + API nos DOIS backends, e a suíte nova:

VERIFICACAO: python3 -m pytest tests/test_signing_keys.py -q && python3 -m pytest tests/test_session_contract.py tests/test_session_video_roundtrip.py -q

## Oráculo

- comando: test -f tests/test_signing_keys.py && python3 -m pytest tests/test_signing_keys.py -q && grep -q signature_key_id packages/domain-schema/src/run_record.py && grep -q signing_key infra/migrations/0013_signing_keys.sql
- exit esperado: 0 — chave registrada/revogada por usuário, submissão
  assinada atribuída (`signature_key_id` na run lida de volta nos dois
  backends), chave alheia 403, revogada 400, legado global intacto.
  Antes do código: exit 1 limpo (teste não existe) — falta de trabalho,
  não oráculo quebrado.
