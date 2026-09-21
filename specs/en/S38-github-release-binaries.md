# S38 — GitHub Release binary distribution

> Decision source: `specs/en/L05-cli-maturation.md` D3/D4. Gives users a real
> install path (download a prebuilt binary) without waiting on crates.io, which
> is blocked by A11 (the vendored `argos-opt` path dep). Only artifacts CI
> actually builds are published — no phantom installer.

## Objective

A git tag `vX.Y.Z` triggers a CI workflow that cross-compiles both binaries,
produces checksummed release archives, and attaches them to a GitHub Release,
so the documented install path becomes "download a release **or** build from
source".

## Scope

In: a tagged-release workflow under `.github/workflows/`; build of
`benchmark-probe` and `canirunit` for at least Linux x86_64 (and, where the CI
image allows, macOS arm64); `SHA256SUMS`; attach archives to the Release; a
docs update so `docs/agent-quickstart.md` / the site `/cli` (L04 S33) offer the
download.
Out: crates.io publish (D4/A11); a one-line installer (D6, still backlog);
signing/notarizing binaries; Windows.

## Contract

1. `.github/workflows/release.yml` (or equivalent): on `push` of a tag matching
   `v*.*.*`, build `--release` binaries for the target matrix, package
   `benchmark-probe-<target>.tar.gz` and `canirunit-<target>.tar.gz`, emit
   `SHA256SUMS`, and create/attach them to the GitHub Release for the tag.
2. The build uses the workspace as-is (vendored `third_party/argos-opt`); no
   publish, no dependency on recovering the original tree.
3. Docs: `docs/agent-quickstart.md` gains a "Download a release" alternative
   next to the from-source build; the honest "no one-line installer yet" line
   stays until D6 ships. `/cli` copy (L04 S33) is updated in that story's cut,
   not here — cross-referenced only.

## Rules

Do not publish an artifact CI did not build in the same run; do not claim a
target the matrix does not produce; never advertise crates.io or an installer
that does not exist (anti-phantom — the analogue of "never use `declare const`
as a workaround": do not conjure a release/target that CI did not produce). Do
not invent a version — the tag is the source of the version. Do not weaken
existing CI jobs to add this one.

- Gate clause: do not invent a number, deadline or source beyond the ones listed; missing data renders as "no data yet".
- Gate clause: never use declare const, a stub success or a fake banner as a workaround — wire the real capability.
## Verified data (2026-09-21)

- Install today = `git clone` + `cargo build --release` + PATH (what `/cli`
  documents).
- `benchmark-probe` builds from the workspace with `third_party/argos-opt`
  vendored; A11 (publish argos-opt) blocks `cargo publish`, not a local
  `cargo build --release`.
- CI workflows already live under `.github/workflows/`.

## Acceptance (each criterion = one command)

1. A tagged-release workflow exists and triggers on version tags: `grep -Eq 'tags:|v\*' .github/workflows/release.yml`
2. It builds both binaries: `grep -q 'benchmark-probe' .github/workflows/release.yml && grep -q 'canirunit' .github/workflows/release.yml`
3. It emits checksums: `grep -qi 'sha256' .github/workflows/release.yml`
4. It attaches to a GitHub Release: `grep -Eqi 'release|softprops/action-gh-release|gh release' .github/workflows/release.yml`
5. Docs offer the download path: `grep -qi 'download' docs/agent-quickstart.md`
6. Honesty preserved (no installer claim yet): `grep -q 'no one-line installer yet' apps/web/site/llms.txt`

## Oráculo

- comando: test -f .github/workflows/release.yml && grep -q 'benchmark-probe' .github/workflows/release.yml && grep -q 'canirunit' .github/workflows/release.yml && grep -qi 'sha256' .github/workflows/release.yml && grep -Eqi 'release' .github/workflows/release.yml && grep -qi 'download' docs/agent-quickstart.md
- exit esperado: 0 — a version tag builds and publishes checksummed binaries
  for both CLIs and the guide offers the download. Before the workflow exists
  the same command fails at the first `test -f` — the clean red state.

## Dependencies / out of scope

- Depends on: nothing (parallel with S37).
- Out: crates.io (A11/D4), installer (D6), binary signing.
