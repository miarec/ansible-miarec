# Plan — MiaRec TLS Enablement

## Summary
MiaRec’s root playbooks already orchestrate PostgreSQL, PGBouncer, and Redis, yet they lack first-class TLS toggles, forcing operators to hand-stitch encrypted deployments even though the underlying roles support TLS. This project surfaces explicit per-service TLS controls, wires them through the playbooks (and recorder role), and supplies a Makefile-driven self-signed certificate workflow so development and Molecule environments can bootstrap easily. By doing so, security-conscious customers can deploy encrypted infrastructure from a single entry point while keeping plaintext defaults for legacy installs.

Deliverables span three phases. Phase 1 introduces the configuration contract (new inventory variables) plus a reusable Makefile that mirrors existing Molecule certificate generation. Phase 2 threads those variables through `prepare-hosts.yml`, `setup-miarec.yml`, and the recorder role (which now ships with TLS support) so enabling TLS updates role inputs, `pg_hba` entries, and MiaRec configs. Phase 3 adds a TLS-focused Molecule scenario with Testinfra assertions and wires it into the GitHub Actions matrix for every supported distro. Each phase ships with its own verification to ensure regressions are caught early.

## 0. References

### 0.1 Specification (Always Read)
- [spec.md](spec.md) — Detailed specification with requirements, assumptions, and acceptance criteria. **Read before any implementation.**

### 0.2 Phase Plans (Read Relevant Phase)
- [plan_phase_1.md](plan_phase_1.md) — Phase 1: Configuration vars & Makefile tooling.
- [plan_phase_2.md](plan_phase_2.md) — Phase 2: Playbook & Recorder Wiring.
- _[plan_phase_3.md](plan_phase_3.md) — To be written after Phase 2 approval._

### 0.3 Research (Read to Understand Codebase)
- [research.md](research.md) — Summarizes existing TLS support in roles, current playbook behavior, Molecule/CI landscape, and tooling gaps.

### 0.4 Source Document (Read if Requested)
- [idea.md](../prs/20260309_tls/idea.md) — Original TLS installation/testing request from the user.

## 1. Software Design Document (SDD)

### 1.1 Goals & Constraints
- Expose optional TLS controls for PostgreSQL, PGBouncer (client/server sides), Redis, and MiaRec recorder while keeping defaults non-TLS.
- Provide self-signed cert generation via Makefile for dev/testing without interfering with production PKI.
- Ensure TLS-enabled paths are exercised by Molecule/CI across all supported distros.
- Constraints: maintain backward compatibility, avoid adding new dependencies, keep Makefile logic idempotent, replicate existing role-level expectations (paths, permissions).

### 1.2 Proposed Architecture (High-level)
- Inventory vars (`vars/db.yml`, `vars/redis.yml`, recorder vars already present) hold TLS flags and file paths.
- `prepare-hosts.yml` conditionally sets role inputs (`postgresql_ssl`, `pgbouncer_client_tls_*`, `redis_tls_*`) plus generates `hostssl` rules when toggles are true.
- `setup-miarec.yml` passes TLS vars to MiaRec web (already supported) and recorder (new INI handling).
- Makefile produces CA/server/client bundles under `certs/<service>/` mirroring `roles/miarecweb/molecule/tls/tasks/certificates.yml`.
- Molecule `tls` scenario imports root playbooks with TLS toggles enabled; Testinfra verifies TLS functionality.

### 1.3 Data Model & Types (Signatures, not full code)
- YAML booleans: `postgresql_tls`, `pgbouncer_client_tls`, `pgbouncer_server_tls`, `redis_tls`, `miarec_db_tls`, `miarec_redis_tls`.
- File path strings: `*_tls_cert_file`, `*_tls_key_file`, `*_tls_ca_file`.
- Recorder INI entries: `sslmode`, `sslrootcert`, `sslcert`, `sslkey` fields appended when TLS on.
- Makefile targets: standard GNU Make syntax, using shell commands to run `openssl`.

### 1.4 Module / File-level Design
- `vars/db.yml`: add TLS toggles/paths for PostgreSQL and PGBouncer (recorder vars already exist in role defaults).
- `vars/redis.yml`: add Redis TLS/paths.
- `vars/web.yml` untouched (already has TLS).
- `roles/miarec` already contains TLS defaults/tasks; only verify usage (no structural changes expected).
- `prepare-hosts.yml`: new `set_fact` blocks inserting TLS role vars; optionally adjust `postgresql_pg_hba_custom`.
- `setup-miarec.yml`: ensure recorder TLS vars propagate so the role activates TLS paths.
- `Makefile`: add TLS cert targets, `clean` helper if needed.
- `molecule/tls/`: new scenario plus Testinfra tests referencing TLS behavior.
- `.github/workflows/ci.yml`: add TLS scenario invocation.

### 1.5 Interfaces & Contracts
- **Ansible vars**: Document exact YAML usage, e.g.:
  ```yaml
  postgresql_tls: true
  postgresql_tls_cert_file: /etc/postgresql/tls/server.crt
  postgresql_tls_key_file: /etc/postgresql/tls/server.key
  postgresql_tls_ca_file: /etc/postgresql/tls/ca.crt
  postgresql_tls_require_clientcert: true
  ```
- **Makefile**:
  ```make
  tls-certs-postgresql:
  	@mkdir -p certs/postgresql
  	openssl genrsa -out certs/postgresql/ca.key 4096
  	...
  ```
- **Recorder INI**: recorder role consumes passed vars; ensure playbooks set `miarec_db_tls*` / `miarec_redis_tls*` so generated INI contains entries such as `sslmode={{ miarec_db_tls_sslmode }}`.
- **Test fixtures**: Testinfra helper fixture with `scope="module"` to expose TLS paths for multiple tests.

### 1.6 Key Algorithms (Pseudo-code)
```
# prepare-hosts.yml (PostgreSQL excerpt)
when: postgresql_tls | bool
  set_fact:
    postgresql_ssl: true
    postgresql_ssl_cert_file: "{{ postgresql_tls_cert_file }}"
    postgresql_ssl_key_file: "{{ postgresql_tls_key_file }}"
    postgresql_ssl_ca_file: "{{ postgresql_tls_ca_file }}"
    postgresql_pg_hba_custom: existing_rules + [
      { type: 'hostssl', database: miarec_db_name, user: miarec_db_user,
        address: item_ip, method: 'md5 clientcert={{ postgresql_tls_require_clientcert | ternary(\"verify-ca\", \"\") }}' }
    ]
```
```
# Makefile TLS generation (simplified)
tls-certs-redis: certs/redis/server.crt
certs/redis/server.crt: certs/redis/ca.crt
	openssl genrsa -out certs/redis/server.key 2048
	openssl req -new -key certs/redis/server.key -out certs/redis/server.csr -config redis.cnf
	openssl x509 -req -in certs/redis/server.csr -CA certs/redis/ca.crt -CAkey certs/redis/ca.key \
	  -out certs/redis/server.crt -days 365 -sha256 -extfile redis.cnf -extensions v3_req
```
```
# setup-miarec.yml (recorder facts)
set_fact:
  miarec_db_tls: "{{ postgresql_tls | default(false) }}"
  miarec_db_tls_sslmode: "{{ postgresql_tls_sslmode | default('verify-ca') }}"
  miarec_db_tls_ca_file: "{{ postgresql_tls_ca_file }}"
  miarec_db_tls_cert_file: "{{ postgresql_tls_cert_file }}"
  miarec_db_tls_key_file: "{{ postgresql_tls_key_file }}"
when: inventory_hostname in groups.recorder
```

### 1.7 Testing Architecture
- **Phase 1**: shell script validating `make tls-certs-all` outputs expected files/permissions; run `ansible-lint` to ensure YAML validity.
- **Phase 2**: targeted Molecule or `ansible-playbook` runs verifying TLS toggles individually; check idempotency; for recorder, confirm INI contains TLS entries.
- **Phase 3**: new `molecule/tls` scenario; Testinfra asserts TLS success/failure behaviors; CI job runs across Ubuntu/Rocky/RHEL distros.
- Fixtures: Testinfra module-scoped fixture returning TLS file mapping to avoid repetitive file lookups.

### 1.8 Edge Cases
- TLS toggles true but cert paths missing → fail-fast message referencing Makefile target.
- Mixed TLS states (e.g., PGBouncer client TLS true, server false) must only set respective role vars.
- Makefile reruns should not overwrite existing certs unless user cleans manually.
- CI runtime increase; ensure job names reflect scenario to diagnose failures.

### 1.9 Observability & Ops
- No new logging endpoints. Document in README/spec that TLS Makefile artifacts are non-production.
- CI status becomes primary indicator; include TLS scenario logs for debugging.

## 2. Phase Breakdown (Approval checkpoint)

### Phase 1. Configuration & Tooling Enablement (complete)
- Goal: Introduce per-service TLS vars and Makefile certificate generation.
- Status: ✅ Delivered via updates to `vars/db.yml`, `vars/redis.yml`, repo-level `Makefile`, and docs in `docs/prs/20260309_tls/idea.md`.
- Acceptance criteria: Vars default to false, documented; Makefile targets (`tls-certs-*`) create CA/server/client bundles with correct permissions; helper instructions provided.
- Tests: `make tls-certs-all` + permission checks; `ansible-lint`.
- Plan doc: [plan_phase_1.md](plan_phase_1.md).

### Phase 2. Playbook & Recorder Wiring (complete)
- Goal: Wire TLS vars through playbooks and recorder role so enabling toggles configures infrastructure + MiaRec recorder.
- Status: ✅ Playbooks now gate role inputs/`pg_hba` entries on TLS toggles and forward recorder/web TLS vars.
- Acceptance criteria: TLS-enabled runs configure PostgreSQL/PGBouncer/Redis/recorder correctly; plaintext defaults remain unaffected; idempotent re-runs succeed.
- Tests: targeted Molecule/`ansible-playbook` runs covering TLS on/off combos, recorder INI assertions.
- Plan doc: [plan_phase_2.md](plan_phase_2.md).

### Phase 3. Molecule & CI TLS Scenario (complete)
- Goal: Add Molecule TLS scenario plus CI coverage across all distros.
- Status: ✅ `molecule/tls/` scenario with Testinfra now runs locally and via GitHub Actions `molecule-tls` matrix.
- Acceptance criteria: `uv run molecule test -s tls` passes locally and in CI; Testinfra confirms TLS-only access.
- Tests: Molecule TLS run for each distro; GitHub Actions logs reviewed.
- Plan doc: [plan_phase_3.md](plan_phase_3.md).

## 3. Living Sections (Mandatory)

> **Instructions for maintainers:**
>
> This plan is a living document. As you make key design decisions, update the plan to record both the decision and the thinking behind it. Record all decisions in the `Decision Log` section.
>
> Maintain the `Progress` section in this plan and in the corresponding phase document. Mark tasks as `[ ]` not started, `[~]` in progress, or `[x]` done.
>
> When you discover optimizer behavior, performance tradeoffs, unexpected bugs, or inverse/unapply semantics that shaped your approach, capture those observations in the `Surprises & Discoveries` section with short evidence snippets (test output is ideal).
>
> If you change course mid-implementation, document why in the `Decision Log` and reflect the implications in `Progress`. Plans are guides for the next contributor as much as checklists for you.
>
> At completion of a major task or the full plan, write an `Outcomes & Retrospective` entry summarizing what was achieved, what remains, and lessons learned.
>
> **This document must describe not just the what but the why for almost everything.**

### 3.1 Progress
- [x] Phase 1: Configuration & Tooling Enablement — vars + Makefile merged; doc snippet published.
- [x] Phase 2: Playbook & Recorder Wiring — TLS toggles drive role inputs/pg_hba + recorder facts.
- [x] Phase 3: Molecule & CI TLS Scenario — TLS scenario + CI job operational (first run 2024‑06‑XX).

### 3.2 Decision Log
- 2024-06-XX — Adopted single repo-level Makefile with shared root CA to keep PostgreSQL, PGBouncer, and Redis artifacts in sync and simplify Molecule bootstrap (`CERTS_DIR` override handles scenario-specific paths).
- 2024-06-XX — Propagated TLS toggles via `set_fact` blocks inside playbooks instead of duplicating vars per host group so inventory defaults remain single-sourced.
- 2024-06-XX — Added dedicated Molecule TLS scenario rather than overloading `default` to preserve fast plaintext CI while still validating TLS end-to-end.

### 3.3 Surprises & Discoveries
- Ensuring TLS-only `pg_hba` entries worked for recorder/web hosts required computing host-specific `private_ip_address` facts even in Molecule (loop logic now guarded when `install_pgbouncer` is true).
- Debian-based Molecule images lacked `python3-pkg-resources`, so the TLS scenario installs it up front to keep recorder role dependencies satisfied.

### 3.4 Outcomes & Retrospective
- All TLS configuration, orchestration, and validation capabilities are merged. Operators flip inventory toggles, run `make tls-certs-*` when needed, and rely on CI to cover TLS regressions.
- Future work: document real-certificate handoff examples (production PKI) if customers request it; otherwise plan can be archived after final handoff.
