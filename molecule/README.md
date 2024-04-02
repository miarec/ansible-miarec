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
 - `MOLECULE_MIARECWEB_VERSION` defines variable `miarecweb_version`, default `2024.1.1.0`
 - `MOLECULE_MIARECWEB_SECRET` defines variabled `miarecweb_secret`, default `secret`
 - `MOLECULE_MIAREC_VERSION` defines variable `miarec_version`, default `7.0.0.100`
 - `MOLECULE_MIAREC_SCREEN_VERSION` defines variable `miarec_screen_version`, default `1.1.0.46`
 - `MOLECULE_MIAREC_LIVEMON_VERSION` defines variable `miarec_livemon_version`, default `0.1.0.183`
 - `MOLECULE_PYTHON_VERSION` defines variable `python_version`, default `3.11.7`
 - `MOLECULE_POSTGRESQL_VERSION` defines variable `postgresql_version`, default `12`
 - `MOLECULE_PGBOUNCER_INSTALL` defines variable `install_pgbouncer`, default `true`
 - `MOLECULE_REDIS_VERSION` defines variable `redis_version`, default `5.0.5`
 - `MOLECULE_ANSIBLE_VERBOSITY` set verbosity for ansible run, like running "ansible -vvv", values 0-3, default 0
