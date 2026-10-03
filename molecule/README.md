# Molecule test this role

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
 - `MOLECULE_DISTRO` OS of docker container to test, default `ubuntu2204`
    List of tested distros
    - `ubuntu2204`
    - `ubuntu2004`
    - `centos7`
 - `MOLECULE_MIARECWEB_VERSION` defines variable `miarecweb_version`, default `2026.8.24.0`
 - `MOLECULE_MIARECWEB_SECRET` defines variabled `miarecweb_secret`, default `secret`
 - `MOLECULE_MIAREC_VERSION` defines variable `miarec_version`, default `2026.8.16.0`
 - `MOLECULE_MIAREC_SCREEN_VERSION` defines variable `miarec_screen_version`, default `2026.8.3.0`
 - `MOLECULE_MIAREC_LIVEMON_VERSION` defines variable `miarec_livemon_version`, default `0.1.0.183`
 - `MOLECULE_PYTHON_VERSION` defines variable `python_version`. Default: `3.12` on RedHat-based distros; the system Python on Ubuntu (3.10 on 22.04, 3.12 on 24.04); `3.11.16` on RHEL 7, where Python is built from source and the value must be a full version
 - `MOLECULE_POSTGRESQL_VERSION` defines variable `postgresql_version`, default `12`
 - `MOLECULE_PGBOUNCER_INSTALL` defines variable `install_pgbouncer`, default `true`
 - `MOLECULE_ANSIBLE_VERBOSITY` set verbosity for ansible run, like running "ansible -vvv", values 0-3, default 0

## Scenario - `decoupled`

Deploys the components on six containers that share one Docker network, like the decoupled inventory in the installation guide. Every container runs the same distro.

| Container | Groups |
|---|---|
| `ansible-miarec-dec-db-<distro>` | `db` |
| `ansible-miarec-dec-redis-<distro>` | `redis` |
| `ansible-miarec-dec-web-<distro>` | `web`, `livemon` |
| `ansible-miarec-dec-celery-<distro>` | `celery`, `celerybeat` |
| `ansible-miarec-dec-rec-<distro>` | `recorder` |
| `ansible-miarec-dec-screen-<distro>` | `screen` |

The converge step sets `private_ip_address` on each host to the container address on the scenario network. The playbooks then open PGBouncer and Redis to the other tiers and allow-list their addresses, which the all-in-one scenario never exercises. The Testinfra tests run per group and check that each tier connects to the database and Redis hosts and that the configuration files point to the right peers.

The scenario accepts the same variables as the `default` scenario.

```
MOLECULE_DISTRO=ubuntu2404 molecule test -s decoupled
```
