# Implement TLS installation and Testing

## Goal
This playbook should be updated to allow for an optional install of services (Postgresql, pgbouncer, and Redis) with TLS based communication between components

## Current State
Submodules support TLS install, root level playbook does not

## Idea
There should be variables like `postgresql_ssl = true` that should be false by default, that will force the install to complete with tls configuration.

When variables are not defined for the location of the Certificates, A `MakeFile` should be included that generates the TLS certificates needed in each scenario

Molecule scenarios should be created to test this installation method as well and added to the CI/CD flow.

## TLS Certificate Helper (Makefile)
- Run `make tls-certs-all` from the repo root to generate self-signed CA/server/client bundles for PostgreSQL, PGBouncer, Redis, MiaRec, and MiaRec web. Artifacts are written to `certs/<service>/`.
- Generated files mirror the expectations from the roles (e.g., `/etc/postgresql/tls/server.crt` or `/etc/miarec/tls/client.crt`), so operators can copy them directly into place or reference them from Molecule scenarios.
- Individual targets exist (`tls-certs-postgresql`, `tls-certs-pgbouncer`, `tls-certs-redis`, `tls-certs-miarec`, `tls-certs-miarecweb`) plus `tls-certs-clean` to remove the `certs/` directory.
- Certificates are intended for development/testing/CI only; production deployments should still provide PKI-issued assets.


## Resources to check
Review submodule configurations that already include support for TLS  installation, including molecule testing
