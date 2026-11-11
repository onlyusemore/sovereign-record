# Security Policy

## Scope

This library provides a signed, append-only record ledger. Its guarantees and boundaries are documented in [`docs/security.md`](docs/security.md) and Section 4 of [`paper.md`](paper.md). Read both before deploying.

## Boundary

The ledger proves what was signed, not that the signer was truthful. It does not protect against key compromise or a signer who writes false content with a valid key. Hold HMAC keys and Ed25519 private keys in a KMS/HSM; never pass them as command-line arguments or commit them.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability in this project.

1. Contact the repository owner directly through GitHub (open a security advisory: Security → Report a vulnerability).
2. Include: the Python version, a minimal reproduction, and the exception output.
3. Allow up to 90 days for a response before public disclosure.

Failures that raise `VerificationError`, `SequenceError`, or `PersistenceError` on tampered input are the design working as intended — report them only with an argument for why the detected state should be considered valid.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 2.0.x   | Yes       |
| 1.1.x   | Yes       |
| 1.0.x   | Best effort |
