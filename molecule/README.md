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

## Scenario - `tls`

End-to-end TLS provisioning that runs `prepare-hosts.yml` and `setup-miarec.yml` with TLS toggles enabled and verifies TLS-only connectivity via Testinfra. The prepare step generates a self-signed certificate set with the repository `Makefile` (`make tls-certs-all`) into the scenario's ephemeral directory, and the playbooks upload it the same way as in production. The scenario never reads or writes `./certs`.

On RHEL 7 and 8, the scenario builds Redis from source, because the distribution packages predate Redis 6.0, the first version with TLS support.

```
MOLECULE_DISTRO=ubuntu2204 molecule test -s tls
```
