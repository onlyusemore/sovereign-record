# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-11-12

### Added
- Full-lifecycle CLI: `keygen` (Ed25519 keypair or HMAC key), `init`, `append` (with `--reasoning` steps file), `verify`, `export-anchor`; `--json` machine-readable output for `append` and `verify` (#9).
- `Ed25519Signer.private_key_hex()`.
- Complete documentation set: `docs/architecture.md`, `docs/security.md`, `docs/quickstart.md`, `docs/api_reference.md`, `docs/comparison.md`; README rewritten (#10).
- PyPI packaging: `pyproject.toml`, console script `sovereign-record`, optional `ed25519` extra (#11).
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`.

## [1.1.0] — 2026-11-12

### Added
- Ed25519 asymmetric signatures: writer holds the private key; any holder of the 32-byte public key can verify the whole chain but cannot append. CLI supports `SOVEREIGN_RECORD_PUBLIC_KEY_HEX` for public verification. Backward compatible: `Ledger(key=...)` still means HMAC-SHA256, and the module imports and works without `cryptography` installed (#6).
- Monotonic-time ordering: `append()` refuses to persist a record whose `monotonic_ns` is older than its predecessor's; `verify()` and on-disk reload reject backdated sequences even when correctly signed (#4, #5).
- `reasoning_state` validation: non-string values raise `TypeError`; strings other than `PRESENT`/`ABSENT` raise `ValueError` (#2).

### Changed
- CI runs the full test suite (was: `test_adversarial.py` only) on Python 3.10–3.13.
- README and `paper.md` updated to match the implementation (32 tests at that release) (#7).
- Workflow action SHAs pinned for supply-chain integrity; `CITATION.cff` bumped to 1.1.0 (#8).

## [1.0.1] — 2026-09-29

- Release metadata update.

## [1.0.0] — 2026-09-29

- Initial public release: signed, chained, append-only record ledger with HMAC-SHA256, external checkpoint verification, auditor CLI, and a six-test adversarial suite covering tamper, truncate, reorder, insert, and coordinated rollback.
