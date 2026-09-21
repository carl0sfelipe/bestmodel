# S42 — `login` + per-user signing-key registration (S23-CLI)

> Decision source: `specs/en/L05-cli-maturation.md` D8. Closes HANDOFF §8 item 2:
> S23's backend (migration `0013` + `POST/GET/DELETE /v1/auth/signing-keys`)
> exists, but the CLI never registers the account's public key, so the
> `signing_key` table is empty and the gate stays single-signer. This story is
> the missing CLI side — using **existing** endpoints only, no backend change.

## Objective

`benchmark-probe login` stores an account token in a config file and registers
the local Ed25519 **public** key with the account via the existing signing-keys
API, so subsequent `--upload`/`--settle-claim`/`contribute` attribute the run to
the user (`signature_key_id`) without hand-pasting a token each time.

## Scope

In: a `login` subcommand that (a) accepts/stores a web-issued account token
(`POST /v1/auth/tokens`) in a config file, (b) reads the local Ed25519 key pair
(the CLI already has one), and (c) registers the **public** key via
`POST /v1/auth/signing-keys`; `login --status`; config-file token/consent
storage.
Out: a device-authorization/OAuth flow in the CLI (needs a new backend endpoint
— backlog line); passkey in the terminal; any new API/migration.

## Contract

1. `cli/benchmark-probe/src/login.rs` (new) + a `login` subcommand in the clap
   tree (S37).
2. Config file `~/.config/benchmark-probe/config` (TOML/JSON): stores the
   account token and the A3 consent choice; `0600` permissions; never logs the
   token.
3. `login` reads the local key at `BENCHMARK_PROBE_KEY_PATH`
   (default `~/.config/benchmark-probe/ed25519.pem`), derives the **public**
   PEM, and `POST /v1/auth/signing-keys` with a label; `login --status` prints
   whether a token is stored and whether a key is registered (`GET`), never the
   token itself.
4. Upload paths read the token from the config file when `BENCHMARK_PROBE_API_TOKEN`
   is unset, and attach `signature_key_id` when a key is registered (the submit
   opt-in path from S23 is unchanged; the legacy global-key path still works
   when no key is registered).

## Rules

Use only the existing endpoints (`POST /v1/auth/tokens`, `POST/GET/DELETE
/v1/auth/signing-keys`) — a diff that adds an endpoint/migration is out of
contract. Never invent an endpoint, a field, or a status the API does not
return. Register the **public** key only; never transmit the private key.
Never print or log the token. Never fabricate a "registered" status the server
did not return (anti-phantom; no stubbed success, the Rust analogue of "never
use `declare const` as a workaround"). Do not weaken existing signing-keys
tests.

## Verified data (2026-09-21)

- S23 backend exists: `infra/migrations/0013_signing_keys.sql`,
  `POST/GET/DELETE /v1/auth/signing-keys` (`apps/public-api/src/routes/`), and
  submit's opt-in `signature_key_id` path; the `signing_key` table is empty.
- The CLI already holds an Ed25519 key pair and signs
  (`sign_submission_payload.rs`); `--upload`/`--settle-claim` today require a
  hand-pasted `BENCHMARK_PROBE_API_TOKEN`.
- HANDOFF §8 item 2 names per-user signing keys as the next step.

## Acceptance (each criterion = one command)

The offline criteria exercise config/key handling without a server; the live
registration leg runs against a local API (`make infra-up` + the API) and is an
integration check.

1. Subcommand exists (was clap usage error): `./target/release/benchmark-probe login --help >/dev/null`
2. `login --status` reports "not logged in" cleanly before any token, non-zero: `HOME=/tmp/bm-empty ./target/release/benchmark-probe login --status; test $? -ne 0`
3. Storing a token writes a `0600` config, token not echoed: `./target/release/benchmark-probe login --token TESTTOKEN --no-register 2>&1 | grep -vq TESTTOKEN && stat -c '%a' ~/.config/benchmark-probe/config | grep -q '^600$'`
4. `--status` after storing shows logged-in without printing the token: `./target/release/benchmark-probe login --status | grep -qi 'logged in' && ! ./target/release/benchmark-probe login --status | grep -q TESTTOKEN`
5. Public-key registration payload is the public PEM (offline dry-run): `./target/release/benchmark-probe login --print-key-registration | grep -q 'PUBLIC KEY'`

## Oráculo

- comando: cargo build --release -p benchmark-probe && ./target/release/benchmark-probe login --token TESTTOKEN --no-register && stat -c '%a' ~/.config/benchmark-probe/config | grep -q '^600$' && ./target/release/benchmark-probe login --status | grep -qi 'logged in' && ! ./target/release/benchmark-probe login --status | grep -q TESTTOKEN
- exit esperado: 0 — `login` stores the token in a `0600` config, reports
  status without leaking it. Before the command exists the same invocation fails
  at clap parsing (usage error, non-zero) — the clean red state. The live
  `POST /v1/auth/signing-keys` registration is an integration check against a
  running API, not part of this offline oracle.

## Dependencies / out of scope

- Depends on: S37 (subcommand tree). Uses only existing S23 endpoints.
- Enables: S41 per-user attribution.
- Out: device-code/OAuth CLI flow (backlog line, needs a new endpoint), passkey
  in terminal, any backend change.
