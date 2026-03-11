# Pull Request Description Template

## 🔍 Summary

Adds first-class TLS enablement across the Ansible playbooks by introducing shared certificate generation tooling, wiring TLS inventory variables through `prepare-hosts.yml`/`setup-miarec.yml`, and providing a Molecule scenario plus CI job that exercises the TLS path end-to-end.

---

## 🎯 Purpose

Operators previously had to handcraft TLS assets even though the downstream roles supported them. This PR exposes consistent TLS toggles, ships a Makefile that mirrors the Molecule certificate generation logic, and ensures both the infrastructure playbooks and recorder/web roles consume those settings so encrypted deployments can be triggered from a single entry point. CI coverage guarantees regressions surface immediately.

---

## 🧪 Testing

How did you verify it works?

* [x] Added/updated tests
* [ ] Ran `pytest`

Notes:
- `PYTHON_VERSION=3.12 uv run molecule test -s tls`
- `PYTHON_VERSION=3.12 uv run molecule verify -s tls`

---

## 📌 Related Issues

Closes #N/A

---

## 🚀 Changes

Brief list of main changes:

* Added a repo-level Makefile that generates CA/server/client bundles for PostgreSQL, PGBouncer, and Redis along with helper docs.
* Introduced TLS inventory variables, `prepare-hosts.yml` wiring (pg_hba hostssl rules, redis TLS facts), and recorder/web fact propagation so services pick up the certs automatically.
* Created a dedicated `molecule/tls` scenario with prepare/converge plays, Redis/PostgreSQL client distribution, Testinfra health checks, and a GitHub Actions matrix job to run it across supported distros.
* Documented the multi-phase TLS implementation plan plus the originating idea/spec files.

---

## ⚠️ Notes for Reviewers

`astral-sh/setup-uv@v4` requires a `GITHUB_TOKEN` when running `act` locally (hosted runners inject it automatically). Set `PYTHON_VERSION=3.12` before invoking Molecule so Ubuntu 24.04 images use the correct interpreter.

---

## 📚 Docs

* [x] Updated docs/prs/20260309_tls/* plan + idea files
