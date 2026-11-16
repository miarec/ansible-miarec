# Research — TLS Enablement for MiaRec Playbooks

## Existing Capabilities
- **Role-level TLS**: Submodule roles already bundle TLS support:
  - `roles/postgresql` exposes `postgresql_ssl*` vars and ships a `molecule/tls` scenario with certificate generation plus positive/negative Testinfra checks (`docs/prs/pr_011_molecule_tls_testing.md`).
  - `roles/pgbouncer` supports `pgbouncer_client_tls` and `pgbouncer_server_tls`, with `tls-client` and `tls-full` Molecule scenarios (`docs/prs/pr_013_tls_support.md`).
  - `roles/redis-new` includes `redis_make_tls` and TLS config template guards, with a dedicated `molecule/tls` scenario verifying TLS-only access.
  - `roles/miarecweb` already consumes TLS via `miarecweb_db_tls*` and `miarecweb_redis_tls*` vars plus a TLS Molecule scenario that generates CA/server/client certs in `/etc/miarecweb/tls` (`molecule/tls/tasks/certificates.yml`).
- **Recorder/Screen gaps**: `roles/miarec` and `roles/miarec-screen` lack TLS variables for database/Redis endpoints; they currently store host:port pairs only.

## Root Playbook Behavior
- `prepare-hosts.yml` orchestrates PostgreSQL, optional PGBouncer, and Redis installs. It sets `pg_hba` rules but never toggles TLS. Certificate paths are unspecified.
- `setup-miarec.yml` wires MiaRec web/recorder/screen hosts to DB/Redis IPs but does not configure TLS-specific vars beyond what MiaRec web already supports.

## Testing & CI
- Repo-level Molecule default scenario (`molecule/default`) runs `prepare-hosts.yml` + `setup-miarec.yml` end-to-end but lacks TLS coverage.
- CI (`.github/workflows/ci.yml`) executes `uv run molecule test` across Ubuntu/Rocky/RHEL distros; adding a TLS scenario will multiply runtime but aligns with user request (“full coverage”).

## Tooling
- No root-level Makefile exists today. TLS cert generation logic lives inside role Molecule tasks (not reusable). New Makefile targets must replicate the CA/server/client chain generation.

## Constraints from Spec
- Service-level TLS toggles (no global flag).
- Makefile must emit self-signed certs when file vars missing, matching paths expected by services (`/etc/postgresql/tls`, `/etc/pgbouncer/tls`, `/etc/redis/tls`).
- Recorder TLS adoption required by project end once role ready.
