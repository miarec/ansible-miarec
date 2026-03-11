# Phase 2 — Playbook & Recorder Wiring

## Goal
Propagate the new TLS variables through `prepare-hosts.yml`, `setup-miarec.yml`, and the MiaRec recorder role so enabling each toggle results in TLS-configured PostgreSQL, PGBouncer (client/server sides), Redis, and recorder application settings without disrupting plaintext defaults.

## Scope
- `prepare-hosts.yml`: conditional role vars, `pg_hba` adjustments, Redis bindings.
- `setup-miarec.yml`: pass TLS vars to recorder hosts so existing recorder TLS logic activates.
- Supporting documentation updates (e.g., README snippets) describing TLS usage within playbooks.

## Tasks
- [x] **PostgreSQL wiring**: In `prepare-hosts.yml`, when `postgresql_tls | bool`, set facts for `postgresql_ssl`, `*_cert_file`, `*_key_file`, `*_ca_file`, and update `postgresql_pg_hba_custom` with `hostssl` entries referencing TLS requirements (`clientcert=verify-ca` when `postgresql_tls_require_clientcert` true). Ensure syntax matches existing YAML structure.
- [x] **PGBouncer wiring**: Conditionally set `pgbouncer_client_tls*` and `pgbouncer_server_tls*` vars before including the role; ensure partial TLS (client vs server) is honored. Adjust instructions for copying certs into `/etc/pgbouncer/tls/`.
- [x] **Redis wiring**: When `redis_tls | bool`, set `redis_make_tls: true` and pass cert paths/auth flag to the role. Update any `redis_bind` logic to keep TLS-only hosts accessible.
- [x] **Recorder wiring**: In `setup-miarec.yml`, pass `miarec_db_tls*` and `miarec_redis_tls*` vars into recorder hosts via `set_fact` or vars files so the updated recorder role emits TLS parameters automatically. Ensure these vars point to the same cert/key paths produced in Phase 1.
- [x] **Documentation**: Update relevant docs (e.g., `docs/prs/20260309_tls/idea.md` or README) describing how to enable TLS per service via playbooks, including required file locations.

## Edge Cases to Address
- Inventory defines TLS cert paths but toggles remain `false` → playbook should leave services plaintext.
- TLS enabled but missing cert file → fail fast with clear message (mention Makefile helper).
- Mixed TLS (e.g., PGBouncer client TLS true, server false) should not inadvertently set server-side TLS.
- Recorder TLS variables should not break when environment lacks TLS (guard `when: miarec_db_tls | bool`).
- Idempotency: rerunning playbooks with TLS enabled should not rewrite cert files or INI entries unnecessarily.

## Acceptance Criteria
- `postgresql_tls`, `pgbouncer_*_tls`, and `redis_tls` toggles change the corresponding role configurations when true, leaving plaintext behavior untouched when false.
- Recorder configuration gains TLS entries matching MiaRec web semantics and only activates when `miarec_db_tls` / `miarec_redis_tls` true.
- Playbook runs with TLS enabled succeed end-to-end for at least one distro; idempotent reruns pass.
- Documentation explains how to enable TLS per component via inventory variables.

## Status
Completed on 2024-06-XX; TLS toggles now drive playbook behavior and docs describe activation requirements.

## Tests (Must be implemented in this phase)
- ✅ `uv run molecule converge -s tls` (scenario exercises `prepare-hosts.yml` + `setup-miarec.yml` with TLS on, covering PostgreSQL, PGBouncer, Redis, recorder/web).
- ✅ Testinfra checks for recorder/web INI TLS entries plus TLS-only connection attempts (see `molecule/tls/tests/test_tls.py`).
- ✅ Manual rerun (`molecule converge` twice) confirmed idempotency and plaintext rejection (non-TLS `psql` / `redis-cli` commands fail as expected).

## Verification Steps
- `uv run molecule converge` (default scenario) with environment vars enabling TLS or custom inventory overlay.
- Use `ansible-playbook prepare-hosts.yml` and `setup-miarec.yml` on test inventory to confirm TLS wiring.
- Inspect `/opt/miarec/releases/.../miarec.ini` for TLS entries and `/etc/postgresql/tls`/`/etc/redis/tls` for usage.
