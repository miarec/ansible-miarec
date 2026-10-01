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
PostgreSQL, PGBouncer, and Redis present server certificates, and MiaRec Web and
the MiaRec recorder present client certificates. Enable TLS with these variables
(for example in `vars/custom.yml`):

```yaml
postgresql_ssl: true
pgbouncer_client_tls: true   # connections from MiaRec to PGBouncer
pgbouncer_server_tls: true   # connections from PGBouncer to PostgreSQL
redis_tls: true
```

TLS private keys are installed readable by root and `miarec_bin_group` only, so
the services that present client certificates (Celery and the recorder) must run
as dedicated users. See [Service users](#service-users). The MiaRec Web role
refuses to configure TLS when Celery runs as root.

The certificates and private keys live on the Ansible control machine under
`certs/` (variable `tls_certs_dir` in `vars/tls.yml`). `prepare-hosts.yml` and
`setup-miarec.yml` upload the files of each service to the right hosts, create
the target directories, and set the ownership and permissions. You do not copy
any file by hand.

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

Provide all the files in the same layout. The CA private key is not needed:

```
certs/
├── root/ca.crt                          # optional, the CA certificate
├── postgresql/{ca.crt,server.crt,server.key}
├── pgbouncer/{ca.crt,server.crt,server.key,client.crt,client.key}
├── redis/{ca.crt,server.crt,server.key}
├── miarec/{ca.crt,client.crt,client.key,redis-ca.crt,redis-client.crt,redis-client.key}
└── miarecweb/{ca.crt,client.crt,client.key,redis-ca.crt,redis-client.crt,redis-client.key}
```

Each `ca.crt` is the CA that the service uses to verify its peers. The
`redis-ca.crt` files are the CA of the Redis server certificate. Mixing the two
options is not supported. If you need it, generate the self-signed set first and
then replace individual files.

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
hostname by default: PGBouncer and MiaRec Web use `sslmode=require` or
`verify-ca`, and the recorder and the Redis client have hostname checks turned
off. If you turn on `verify-full` or the `*_check_hostname` variables, issue the
server certificates with the addresses that the clients connect to
(`make tls-certs-postgresql TLS_SAN_POSTGRESQL=IP:10.0.0.5`).
