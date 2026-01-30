This file provides guidance to coding agent when working with code in this repository.

## Project Overview

Ansible playbooks for deploying MiaRec call recording applications on Linux (RHEL/CentOS 7-9, Rocky 8-9, Ubuntu 20.04-24.04).

## Commands

### Using uv (recommended)

This project uses `uv` for dependency management:

```bash
# Install dependencies (creates .venv automatically)
uv sync

# Run ansible-lint
uv run ansible-lint

# Run molecule tests
uv run molecule test

# Run molecule test for specific distro
MOLECULE_DISTRO=ubuntu2204 uv run molecule test
```

### Molecule Test Variables

Environment variables for molecule tests:
- `MOLECULE_DISTRO` - Target OS (ubuntu2004, ubuntu2204, ubuntu2404, centos7, rockylinux8, rockylinux9, rhel7, rhel8, rhel9)
- `MOLECULE_MIARECWEB_VERSION`, `MOLECULE_MIAREC_VERSION`, `MOLECULE_MIAREC_SCREEN_VERSION`
- `MOLECULE_POSTGRESQL_VERSION`, `MOLECULE_REDIS_VERSION`, `MOLECULE_PYTHON_VERSION`

### Running Playbooks

```bash
# Full deployment
ansible-playbook -i <inventory> provision-all.yml

# Or separately:
ansible-playbook -i <inventory> prepare-hosts.yml   # Infrastructure (DB, Redis, Apache, Python)
ansible-playbook -i <inventory> setup-miarec.yml    # MiaRec applications
```

## Architecture

### Main Playbooks

- `provision-all.yml` - Runs both prepare-hosts and setup-miarec
- `prepare-hosts.yml` - Installs infrastructure: PostgreSQL, PGBouncer (optional), Redis, Apache, Python, Sox
- `setup-miarec.yml` - Deploys MiaRec applications: miarecweb, miarec recorder, miarec-screen, miarec_livemon

### Inventory Host Groups

Playbooks expect these host groups:
- `db` - PostgreSQL/PGBouncer servers
- `redis` - Redis servers
- `web` - Web frontend (Apache + miarecweb)
- `celery` - Celery workers
- `celerybeat` - Celery beat scheduler
- `recorder` - MiaRec recorder instances
- `screen` - Screen recording controllers
- `livemon` - Live monitoring servers
- `lb` - HAProxy load balancers (optional)

Hosts must define `private_ip_address` variable for inter-component connectivity.

### Roles

Each role follows standard Ansible structure with OS-specific vars in `vars/RedHat.yml` and `vars/Debian.yml`:
- `postgresql`, `pgbouncer`, `redis-new` - Database infrastructure
- `apache`, `python`, `sox` - Web dependencies
- `miarecweb` - Web UI, includes Apache config and Celery services
- `miarec` - Call recorder
- `miarec-screen` - Screen recorder controller
- `miarec_livemon` - Live monitoring
- `miarecweb-lb` - HAProxy configuration
- `letsencrypt`, `iptables`, `disable-selinux` - System utilities

### Variable Files

- `vars/db.yml` - Database credentials and settings
- `vars/web.yml` - Web application settings
- `vars/redis.yml` - Redis configuration
- `vars/custom.yml` - Optional site-specific overrides (not in repo)

## Ansible-lint

Configured in `.ansible-lint`. Excludes `roles/` directory and skips various yaml/name rules.
