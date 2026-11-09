# Ansible playbook to install MiaRec applications

Documentation: [Installation of MiaRec on Linux using Ansible](https://www.miarec.com/doc/administration-guide/doc918)

## Service users

By default, the MiaRec services run as root, which keeps existing deployments
working when you rerun the playbooks. To run them as dedicated accounts, set the
variables in `vars/custom.yml` or in the inventory. The roles create the users
and groups when they do not exist, and Apache is added to the shared group.
Example `vars/custom.yml`:

```yaml
# Shared group of all MiaRec services. Owns production.ini and the TLS private keys.
miarec_bin_group: miarec

# MiaRec recorder
miarec_bin_user: miarec

# Celery workers and beat scheduler (Apache keeps its own user)
miarecweb_celery_user: celery

# Screen recording controller
miarec_screen_bin_user: miarec
miarec_screen_bin_group: miarec

# Live monitoring
miarec_livemon_bin_user: miarec
miarec_livemon_bin_group: miarec
```

Switching an existing deployment from root to dedicated users changes the
ownership of the installed files and requires a service restart, which the
playbooks perform. The `molecule/tls` scenario uses this configuration.

## TLS certificates

The playbooks can encrypt the connections between MiaRec components with TLS:
PostgreSQL, PGBouncer, and Redis present server certificates, and MiaRec Web,
the MiaRec recorder, and the screen controller present client certificates.
Enable TLS with these variables (for example in `vars/custom.yml`):

```yaml
postgresql_ssl: true
pgbouncer_client_tls: true   # connections from MiaRec to PGBouncer
redis_tls: true
```

`pgbouncer_server_tls`, the connection from PGBouncer to PostgreSQL on the same
host, follows `postgresql_ssl`. Set it in `vars/custom.yml` only to override.

By default, the servers check a client certificate only when the client presents
one, and a client with the right password logs in without a certificate. To
require the certificate as well, set these variables too:

```yaml
postgresql_ssl_require_clientcert: true   # clientcert=verify-ca on the hostssl rules
pgbouncer_client_tls_sslmode: verify-ca   # instead of require
```

TLS private keys are installed readable by root and `miarec_bin_group` only, so
the services that present client certificates (Celery, the recorder, and the
screen controller) must run as dedicated users. See [Service users](#service-users).
The MiaRec Web role refuses to configure TLS when Celery runs as root.

The certificates and private keys live on the Ansible control machine under
`certs/` (variable `tls_certs_dir` in `vars/tls.yml`). Each role uploads the
files of its own service, creates the target directories, sets the ownership
and permissions, and restarts the service when a file changed. You do not copy
any file by hand.

To manage the files of a service outside Ansible, set its `*_src` variables
from `vars/tls.yml` to an empty string in `vars/custom.yml`. The role then
expects the files at the configured paths on the host and leaves them alone.

### Option 1: self-signed certificates

```bash
make tls-certs-all        # or tls-certs-<service> for one service
make tls-certs-validate
```

The first run creates a root CA in `certs/root/` and one directory per service.
The CA and the service certificates are valid for 10 years (`TLS_CA_DAYS` and
`TLS_DAYS`). The targets are idempotent: they create only the files that are
missing and never overwrite an existing file. To reissue a certificate, delete it
and run the target again. Run `make help` for the list of targets and `make tls-certs-all TLS_SAN=IP:10.0.0.5`
style overrides (see the header of the `Makefile`).

### Option 2: certificates issued by your own CA

Provide the files of the services in the same layout. The `root/` directory
belongs to the self-signed option and is not needed. Only the service files are
uploaded to the hosts:

```
certs/
├── postgresql/{ca.crt,server.crt,server.key}
├── pgbouncer/{ca.crt,server.crt,server.key,client.crt,client.key}
├── redis/{ca.crt,server.crt,server.key}
├── miarec/{db-ca.crt,db-client.crt,db-client.key,redis-ca.crt,redis-client.crt,redis-client.key}
└── miarecweb/{db-ca.crt,db-client.crt,db-client.key,redis-ca.crt,redis-client.crt,redis-client.key}
```

Each `ca.crt` is the CA that the service uses to verify its peers. The MiaRec
Web and recorder clients have one set of files for each server: the `db-*` files
for PGBouncer or PostgreSQL, and the `redis-*` files for Redis. `db-ca.crt` and
`redis-ca.crt` are the CAs of the server certificates. Mixing the two
options is not supported. If you need it, generate the self-signed set first and
then replace individual files.

If your CA issues the certificates through an intermediate CA, append the
intermediate certificate to each certificate file after the leaf certificate,
in the order a TLS server sends the chain (the `fullchain.pem` layout). The
`ca.crt` files then hold the root alone. Placing the intermediate in the
`ca.crt` files instead works as well, but every host that verifies a
certificate must then receive the new file when the intermediate changes.

### Validation

```bash
make tls-certs-validate
```

The command works for both options. It checks that every file exists, that each
private key matches its certificate, that no certificate has expired, and that
every certificate is trusted by the CA file of the service that verifies it (for
example, that PostgreSQL's `ca.crt` trusts the MiaRec Web client certificate).
It exits with a non-zero status when it finds a problem.

### Hostname verification

The generated server certificates carry `DNS:localhost, IP:127.0.0.1` as subject
alternative names. This is sufficient because no component verifies the server
hostname by default: the clients verify that the CA signed the server
certificate (`sslmode=verify-ca` for the database, `ssl_cert_reqs=required` for
Redis) but do not compare the hostname. PGBouncer connects to PostgreSQL with
`sslmode=require`. If you turn on `verify-full` or the `*_check_hostname` variables, issue the
server certificates with the addresses that the clients connect to
(`make tls-certs-postgresql TLS_SAN_POSTGRESQL=IP:10.0.0.5`).

## Testing

The playbooks are tested with Molecule. For the scenarios and their variables, see [molecule/README.md](molecule/README.md).

Each `make test-*` target runs one configuration that CI tests, on Ubuntu 24.04 by default. To list the targets, run `make help`.

```
uv sync
make test-decoupled-tls
make test-decoupled-tls DISTRO=rockylinux9
```

| Target | Containers | TLS | PGBouncer |
|---|---|---|---|
| `test-default` | One for all components | No | Yes |
| `test-default-no-pgbouncer` | One for all components | No | No |
| `test-tls` | One for all components | Yes | Yes |
| `test-tls-no-pgbouncer` | One for all components | Yes | No |
| `test-tls-clientcert` | One for all components | Yes, client certificates required | Yes |
| `test-tls-no-pgbouncer-clientcert` | One for all components | Yes, client certificates required | No |
| `test-decoupled` | One per tier | No | Yes |
| `test-decoupled-no-pgbouncer` | One per tier | No | No |
| `test-decoupled-tls` | One per tier | Yes | Yes |
| `test-decoupled-tls-no-pgbouncer` | One per tier | Yes | No |
| `test-decoupled-tls-postgresql-ssl` | One per tier | Yes, also from PGBouncer to PostgreSQL | Yes |

Production deployments rarely use the configurations without PGBouncer, with TLS from PGBouncer to PostgreSQL, or with client certificates required. CI runs them on Ubuntu 24.04 only.

To run another Molecule command, set `MOLECULE_COMMAND`. The next command for the same configuration and distro reuses the containers:

```
make test-decoupled-tls MOLECULE_COMMAND=converge
make test-decoupled-tls MOLECULE_COMMAND=verify
make test-decoupled-tls MOLECULE_COMMAND=destroy
```

### Run tests in parallel

Every configuration has its own container names and Molecule state directory, under `~/.cache/molecule/ansible-miarec/<configuration>-<distro>`. You can run any number of configurations and distros at the same time:

```
for d in ubuntu2404 rockylinux9 rhel7 rhel8 rhel9; do
  make test-decoupled DISTRO=$d </dev/null > /tmp/molecule-decoupled-$d.log 2>&1 &
done
make test-decoupled-tls-no-pgbouncer </dev/null > /tmp/molecule-dtls-no-pgbouncer.log 2>&1 &
wait
```

Don't run the same configuration on the same distro twice at the same time: both runs use the same containers.

If you run `molecule` directly, give each run its own `MOLECULE_EPHEMERAL_DIRECTORY`. Otherwise, the runs share Molecule state and break each other. To run two configurations of one scenario on the same distro, also give each run its own `MOLECULE_INSTANCE_SUFFIX`, which Molecule appends to the container names.

### Raise the inotify instance limit

Before you run several scenarios at the same time, raise the host's inotify instance limit:

```
echo 'fs.inotify.max_user_instances = 1024' | sudo tee /etc/sysctl.d/99-inotify.conf
sudo sysctl -w fs.inotify.max_user_instances=1024
```

Every test container runs systemd, which uses inotify instances: about 5–10 for each RHEL or Rocky Linux container and up to 20 for each Ubuntu container. The kernel counts instances per host user, and root in every container is root on the host, so all containers share one limit. The default limit is 128, which two `decoupled` scenarios (12 containers) can exceed. When the limit runs out, systemd in the next container fails to start, and the run fails with `Failed to connect to bus: No such file or directory`.
