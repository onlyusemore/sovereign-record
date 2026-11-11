# Contributing

Thanks for your interest in `sovereign-record`. This project has a deliberately small surface; keeping it that way is a feature.

## Design constraints (read first)

Any contribution must preserve:

1. **Fail-closed behavior** — detected inconsistencies raise typed exceptions; the ledger never repairs or guesses.
2. **Keys out of argv** — signing material comes from the environment or out-of-band channels, never command-line arguments.
3. **Standard-library HMAC path** — the module must import and HMAC ledgers must work without the `cryptography` package.
4. **Single-module simplicity** — the core implementation stays in `sovereign_record.py`; additions must justify their weight.
5. **Verified claims only** — documentation and the paper must match the code; test counts in docs must equal actual counts.

## Workflow

1. Fork or branch from `main`.
2. Make your change with tests. The full suite must pass:
   ```bash
   python -m pip install pytest cryptography
   python -m pytest -q
   ```
3. Open a pull request against `main`. CI runs the suite on Python 3.10–3.13 and must be green.
4. Keep PRs small and single-purpose (one feature or fix per PR).

## Reporting security issues

Do not open public issues for suspected vulnerabilities in the design. See `docs/security.md` for the threat model; responsible disclosure is preferred — contact the repository owner directly.

## Reporting bugs

Open an issue with: the Python version, a minimal reproduction, and the exception traceback. Records that fail closed are working as designed — include your reasoning about why the behavior is wrong before suggesting a change.
