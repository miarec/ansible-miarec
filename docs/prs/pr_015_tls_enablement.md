# Pull Request Description Template

## 🔍 Summary

Adds end-to-end TLS automation for MiaRec deployments: certificate generation tooling, inventory/playbook wiring for PostgreSQL, PGBouncer, Redis, MiaRec Web/Recorder, and Molecule coverage (plus CI) that proves the TLS posture across Ubuntu 22.04/24.04 and EL9 distros.

---

## 🎯 Purpose

Previously, enabling TLS meant manually minting certificates, sprinkling host-specific overrides, and hoping downstream roles stayed in sync. This PR standardizes TLS inputs (one inventory switch per component), wires the playbooks to distribute certs/keys, and introduces repeatable Molecule scenarios with shared CA generation so encrypted topologies can be tested locally and in CI before landing changes.

---

## 🧪 Testing

How did you verify it works?

* [x] Added/updated tests
* [ ] Ran `pytest`

Notes:
- `MOLECULE_DISTRO=ubuntu2404 uv run molecule test`
- `MOLECULE_DISTRO=ubuntu2404 uv run molecule test -s tls`
- `MOLECULE_DISTRO=rhel9 uv run molecule test`
- `MOLECULE_DISTRO=rhel9 uv run molecule test -s tls`
- `MOLECULE_DISTRO=rockylinux9 uv run molecule test`
- `MOLECULE_DISTRO=rockylinux9 uv run molecule test -s tls`

---

## 📌 Related Issues

Closes #N/A

---

## 🚀 Changes

Brief list of main changes:

* Added a Makefile-driven TLS toolkit plus docs so operators (and Molecule) can mint consistent CA/server/client bundles for PostgreSQL, PGBouncer, and Redis.
* Extended inventory defaults (`vars/db.yml`, `vars/redis.yml`) and `prepare-hosts.yml`/`setup-miarec.yml` to propagate TLS facts, update pg_hba rules, and configure MiaRec Web/Recorder + Redis with the generated certs.
* Created/enhanced the `molecule/tls` scenario (prepare tasks, Testinfra suite) and taught GitHub Actions to run it across Ubuntu/Rocky/RHEL, alongside distro-aware verifier fixes.
* Updated docs/prs planning notes plus `.gitignore`, workflow matrix, and supporting configs to reflect the TLS-first workflow.

---

## ⚠️ Notes for Reviewers

TLS Molecule runs are lengthy (~12–15 minutes per distro) because they execute the full `prepare-hosts.yml` + `setup-miarec.yml` stack; plan CI time accordingly. When running locally, ensure Docker has enough memory (>=4 GB) and set `MOLECULE_DISTRO` explicitly to avoid pulling the wrong systemd image.

---

## 📚 Docs

* [x] Updated docs/prs/20260309_tls/* plan + idea files
