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
 - `MOLECULE_MIARECWEB_VERSION` defines variable `miarecweb_version`, default `2026.1.11.236`
 - `MOLECULE_MIARECWEB_SECRET` defines variabled `miarecweb_secret`, default `secret`
 - `MOLECULE_MIAREC_VERSION` defines variable `miarec_version`, default `2025.12.2.13`
 - `MOLECULE_MIAREC_SCREEN_VERSION` defines variable `miarec_screen_version`, default `2024.6.2.0`
 - `MOLECULE_MIAREC_LIVEMON_VERSION` defines variable `miarec_livemon_version`, default `0.1.0.183`
 - `MOLECULE_PYTHON_VERSION` overrides the `python_version` passed to the playbooks (defaults to `3.12` on Rocky/RHEL and is optional on Debian/Ubuntu)
 - `MOLECULE_POSTGRESQL_VERSION` defines variable `postgresql_version`, default `12`
 - `MOLECULE_PGBOUNCER_INSTALL` defines variable `install_pgbouncer`, default `true`
 - `MOLECULE_ANSIBLE_VERBOSITY` set verbosity for ansible run, like running "ansible -vvv", values 0-3, default 0

## Scenario - `tls`

End-to-end TLS provisioning that runs `prepare-hosts.yml` and `setup-miarec.yml` with TLS toggles enabled, copies self-signed certificates via the repository `Makefile`, and verifies TLS-only connectivity via Testinfra.

```
MOLECULE_DISTRO=ubuntu2204 molecule test -s tls
```
