# Molecule test this role

| Scenario | Containers | TLS |
|---|---|---|
| `default` | One container with all components | No |
| `tls` | One container with all components | Yes |
| `decoupled` | One container per tier | No |
| `decoupled-tls` | One container per tier | Yes |

The repository `Makefile` has a `test-*` target for each configuration that CI tests, for example `make test-decoupled-tls DISTRO=rockylinux9`. For the targets, see [Testing](../README.md#testing).

The scenarios share the plays in `shared/`: the install variables, the container addresses of the decoupled scenarios, and the TLS variables and certificates of the TLS scenarios. Each scenario's `converge.yml` and `prepare.yml` import the plays it needs.

## Scenario - `default`

Run Molecule test
```
molecule test
```

Run test with variable example
```
MOLECULE_DISTRO=centos7 MOLECULE_MIARECWEB_VERSION=8.0.0.3909 molecule test
```

### Variables
 - `MOLECULE_DISTRO` OS of docker container to test, default `ubuntu2404`. For the tested distros, see `.github/workflows/ci.yml`.
 - `MOLECULE_MIARECWEB_VERSION` defines variable `miarecweb_version`, default `2026.8.24.0`
 - `MOLECULE_MIARECWEB_SECRET` defines variabled `miarecweb_secret`, default `secret`
 - `MOLECULE_MIAREC_VERSION` defines variable `miarec_version`, default `2026.8.16.0`
 - `MOLECULE_MIAREC_SCREEN_VERSION` defines variable `miarec_screen_version`, default `2026.8.3.0`
 - `MOLECULE_MIAREC_LIVEMON_VERSION` defines variable `miarec_livemon_version`, default `0.1.0.183`
 - `MOLECULE_PYTHON_VERSION` defines variable `python_version`. Default: `3.12` on RedHat-based distros; the system Python on Ubuntu (3.10 on 22.04, 3.12 on 24.04); `3.11.16` on RHEL 7, where Python is built from source and the value must be a full version
 - `MOLECULE_POSTGRESQL_VERSION` defines variable `postgresql_version`, default `15`
 - `MOLECULE_INSTALL_PGBOUNCER` defines variable `install_pgbouncer`, default `true`. With `false`, the scenario skips PGBouncer, and the clients connect to PostgreSQL directly. Every scenario accepts it.
 - `MOLECULE_INSTANCE_SUFFIX` is appended to the container and network names, default empty. Two runs of one scenario on the same distro need different suffixes and different `MOLECULE_EPHEMERAL_DIRECTORY` values. The `make test-*` targets set both.
 - `MOLECULE_ANSIBLE_VERBOSITY` set verbosity for ansible run, like running "ansible -vvv", values 0-3, default 0

## Scenario - `tls`

End-to-end TLS provisioning that runs `prepare-hosts.yml` and `setup-miarec.yml` with TLS toggles enabled and verifies TLS-only connectivity via Testinfra. The prepare step generates a self-signed certificate set with the repository `Makefile` (`make tls-certs-all`) into the scenario's ephemeral directory, and the playbooks upload it the same way as in production. The scenario never reads or writes `./certs`.

On RHEL 7 and 8, the scenario builds Redis from source, because the distribution packages predate Redis 6.0, the first version with TLS support.

The services run as dedicated users, because the TLS private keys are readable by the `miarec` group only. The scenario runs the process-user tests of the `default` scenario too.

```
MOLECULE_DISTRO=ubuntu2404 molecule test -s tls
```

## Scenario - `decoupled`

Deploys the components on six containers that share one Docker network, like the decoupled inventory in the installation guide. Every container runs the same distro.

| Container | Groups |
|---|---|
| `ansible-miarec-dec-db-<distro><suffix>` | `db` |
| `ansible-miarec-dec-redis-<distro><suffix>` | `redis` |
| `ansible-miarec-dec-web-<distro><suffix>` | `web`, `livemon` |
| `ansible-miarec-dec-celery-<distro><suffix>` | `celery`, `celerybeat` |
| `ansible-miarec-dec-rec-<distro><suffix>` | `recorder` |
| `ansible-miarec-dec-screen-<distro><suffix>` | `screen` |

The converge step sets `private_ip_address` on each host to the container address on the scenario network. The playbooks then open PGBouncer and Redis to the other tiers and allow-list their addresses, which the all-in-one scenario never exercises. The Testinfra tests run per group and check that each tier connects to the database and Redis hosts and that the configuration files point to the right peers.

The scenario accepts the same variables as the `default` scenario.

```
MOLECULE_DISTRO=ubuntu2404 molecule test -s decoupled
```

## Scenario - `decoupled-tls`

The `decoupled` scenario with TLS on every connection to PostgreSQL, PGBouncer, and Redis. It combines the plays of the `decoupled` and `tls` scenarios: the same six containers (named `ansible-miarec-dtls-*`), the same certificate set, and the same TLS variables. It runs the `decoupled` tests, which read `TLS_ENABLED` from the scenario environment. With TLS, the tests also check that the clients connect over TLS and that PGBouncer, PostgreSQL, and Redis reject plaintext connections and untrusted client certificates.

PGBouncer and PostgreSQL run on the same host, so the connection between them stays plaintext by default. Encrypting it costs CPU time and protects nothing that leaves the host.

The scenario accepts the same variables as the `default` scenario, plus:

 - `MOLECULE_POSTGRESQL_SSL` turns on TLS between PGBouncer and PostgreSQL, default `false`. Without PGBouncer, PostgreSQL always uses TLS, because the clients connect to it directly.

```
MOLECULE_DISTRO=ubuntu2404 molecule test -s decoupled-tls
```

## Edge cases

Production deployments rarely use these configurations, but the playbooks support them. CI runs them on Ubuntu 24.04 only.

| Command | Make target | What it checks |
|---|---|---|
| `MOLECULE_POSTGRESQL_SSL=true molecule test -s decoupled-tls` | `test-decoupled-tls-postgresql-ssl` | PGBouncer connects to PostgreSQL over TLS, although both run on the same host. |
| `MOLECULE_INSTALL_PGBOUNCER=false molecule test -s decoupled-tls` | `test-decoupled-tls-no-pgbouncer` | The clients connect to PostgreSQL on another host directly, over TLS. |
| `MOLECULE_INSTALL_PGBOUNCER=false molecule test -s decoupled` | `test-decoupled-no-pgbouncer` | The clients connect to PostgreSQL on another host directly, without TLS. |
| `MOLECULE_INSTALL_PGBOUNCER=false molecule test` | `test-default-no-pgbouncer` | All components on one host, without PGBouncer. |
| `MOLECULE_INSTALL_PGBOUNCER=false molecule test -s tls` | `test-tls-no-pgbouncer` | All components on one host, without PGBouncer, with TLS. |
