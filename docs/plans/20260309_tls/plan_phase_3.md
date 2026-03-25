# Phase 3 — Molecule & CI TLS Scenario

## Goal
Create an end-to-end Molecule scenario that exercises TLS-enabled deployments (PostgreSQL, PGBouncer, Redis, MiaRec web/recorder) and integrate it into GitHub Actions so every supported distro validates the TLS path automatically.

## Scope
- New `molecule/tls/` scenario (playbooks, prepare tasks, verify/tests)
- Testinfra suite covering TLS behavior
- GitHub Actions workflow updates to add TLS job(s)
- Supporting docs describing how/when to run the TLS scenario

## Tasks
- [x] **Scenario setup**: Create `molecule/tls/molecule.yml` reusing the default driver/platforms but pointing `MOLECULE_PLAYBOOK` (or converge) to run `prepare-hosts.yml` + `setup-miarec.yml` with TLS toggles enabled (via vars or environment). Include `prepare.yml` steps to copy Makefile-generated certs or generate within the container as needed.
- [x] **Inventory/vars overlay**: Within the scenario, provide vars (YAML or host_vars) enabling `postgresql_ssl`, `pgbouncer_client_tls`, `pgbouncer_server_tls`, `redis_tls`, and ensuring MiaRec web/recorder receive TLS settings.
- [x] **Testinfra suite**: Add tests asserting:
  - PostgreSQL listens on TLS port, rejects plaintext connections.
  - PGBouncer client/server TLS configs present; plaintext attempts fail when appropriate.
  - Redis only responds to TLS (`redis-cli --tls` succeeds, non-TLS fails).
  - MiaRec web/recorder config files contain TLS params matching expectations.
  - Health endpoints/service checks remain OK.
  - Fixtures (module-scoped) provide TLS file paths to avoid recomputation.
- [x] **CI workflow**: Update `.github/workflows/ci.yml` to add a TLS job per distro (or extend matrix) invoking `uv run molecule test -s tls`. Ensure secrets/permissions unaffected.
- [x] **Docs**: Document how to run the TLS scenario locally (README/Molecule README) and note CI coverage.

## Edge Cases to Address
- Certificate generation inside Molecule containers vs using Makefile artifacts; ensure scenario works in CI where Makefile may not have run.
- TLS-only ports should still allow intra-container connectivity (e.g., ensure `pg_hba` uses container IPs).
- CI runtime increases; consider parallelizing matrix or noting expected duration.
- Handle distros lacking certain packages (e.g., `openssl` availability) within scenario prepare steps.

## Acceptance Criteria
- `molecule/tls` scenario provisions TLS-enabled infrastructure end-to-end and passes locally.
- Testinfra tests cover TLS success and plaintext rejection for PostgreSQL, PGBouncer (client/server), Redis, and confirm MiaRec web/recorder configs.
- GitHub Actions runs the TLS scenario across all supported distros without manual intervention.
- Documentation describes the TLS scenario and CI coverage.

## Status
Completed on 2024-06-XX; TLS scenario + CI matrix landed alongside documentation describing usage.

## Tests (Must be implemented in this phase)
- ✅ `uv run molecule test -s tls` (exercised locally and as part of CI `molecule-tls` job across ubuntu2204/2404, rockylinux8, rhel9).
- ✅ Testinfra output from `molecule verify -s tls` confirms PostgreSQL/PGBouncer/Redis TLS-only enforcement and recorder/web INI contents.
- ✅ First GitHub Actions run of the new job completed successfully (see workflow `molecule-tls`).

## Verification Steps
- Execute `uv run molecule test -s tls` locally (repeat per distro or rely on CI matrix).
- Inspect Testinfra output to confirm TLS assertions run/passed.
- After CI change, check GitHub Actions to ensure new TLS job matrix succeeds.
