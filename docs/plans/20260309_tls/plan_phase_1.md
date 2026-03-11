# Phase 1 — Configuration & Tooling Enablement

## Goal
Introduce the per-service TLS configuration surface and Makefile-based certificate generation so operators and Molecule runs can supply consistent cert bundles before wiring TLS through the infrastructure playbooks.

## Scope
- Inventory variables in `vars/db.yml` and `vars/redis.yml`
- Repository-level `Makefile` targets + helper scripts (if any)
- Documentation snippets describing usage (README or docs/prs area)

## Tasks
- [x] **Add PostgreSQL TLS vars** (`postgresql_tls`, `postgresql_tls_cert_file`, `postgresql_tls_key_file`, `postgresql_tls_ca_file`, `postgresql_tls_require_clientcert`) to `vars/db.yml` with defaults + comments.
- [x] **Add PGBouncer TLS vars** for client/server sides (`pgbouncer_client_tls`, `pgbouncer_client_tls_*`, `pgbouncer_server_tls`, `pgbouncer_server_tls_*`) with explicit YAML syntax and references to canonical file paths.
- [x] **Add Redis TLS vars** (`redis_tls`, `redis_tls_cert_file`, `redis_tls_key_file`, `redis_tls_ca_file`, `redis_tls_auth_clients`) to `vars/redis.yml`.
- [x] **Create Makefile** in repo root with targets:
  - `tls-certs-postgresql` (generate CA/server/client certs under `certs/postgresql/`)
  - `tls-certs-pgbouncer` (reuse PostgreSQL CA, emit server/client certs under `certs/pgbouncer/`)
  - `tls-certs-redis` (dedicated CA/server/client under `certs/redis/` with SANs for localhost + 127.0.0.1)
  - `tls-certs-all` (depends on the three targets)
  - Optional `tls-certs-clean` to remove generated artifacts
- [x] **Document instructions** (e.g., `docs/prs/20260309_tls/idea.md` or README snippet) explaining how to run the Makefile targets and where to copy resulting files on hosts.

## Edge Cases to Address
- Re-running `make tls-certs-*` should not overwrite existing certs unless the user cleans; guard via `test -f` or Make dependencies.
- Warn users that generated certs are self-signed and not for production; include this in documentation output.
- Ensure Windows/macOS make users can run the targets (stick to POSIX shell commands already used elsewhere).
- Handle missing `openssl` by emitting a clear error message in Makefile (e.g., `command -v openssl` check).

## Acceptance Criteria
- All new TLS variables exist with defaults, comments, and canonical paths matching role expectations.
- Makefile targets generate CA/server/client cert bundles with the same SANs/permissions as existing Molecule scripts.
- Documentation explains usage and cautions about non-production certs.

## Status
Completed on 2024-06-XX; TLS vars landed in inventory defaults, Makefile committed, and documentation updated.

## Tests (Must be implemented in this phase)
- ✅ `make tls-certs-all` (executed via Molecule TLS `prepare.yml`, verified outputs + permissions).
- ✅ Manual permission inspection through Molecule `copy` tasks (keys 0600, certs 0644) during TLS scenario prep.
- ✅ `uv run ansible-lint` (CI `lint` job).

## Verification Steps
- Run `make tls-certs-all`; inspect `certs/postgresql`, `certs/pgbouncer`, `certs/redis`.
- Execute `find certs -type f -ls` (or similar) to confirm permissions.
- Run `uv run ansible-lint`.
