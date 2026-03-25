# Ansible playbook to install MiaRec applications

Documentation: [Installation of MiaRec on Linux using Ansible](https://www.miarec.com/doc/administration-guide/doc918)

## TLS Certificate Helper

Use the Makefile targets to bootstrap development certificates when you do not have PKI-issued assets:

```bash
make tls-certs-all            # or tls-certs-<service>
```

Artifacts land in `certs/<service>/`. Each directory contains a CA plus service-specific `server.*`, `client.*`, and (when applicable) `redis-client.*` bundles that mirror the paths referenced in the playbooks (`/etc/<service>/tls/...`).

To copy them to a host:

```bash
scp certs/postgresql/{server.crt,server.key,ca.crt} user@host:/tmp/
scp certs/postgresql/{client.crt,client.key} user@host:/tmp/
```

On the remote machine, move files into place and apply strict permissions (keys `0600`, certs `0644`) before running the playbooks:

```bash
sudo install -d -m 0750 -o postgres -g postgres /etc/postgresql/tls
sudo install -m 0600 -o postgres -g postgres /tmp/server.key /etc/postgresql/tls/server.key
sudo install -m 0644 -o postgres -g postgres /tmp/server.crt /etc/postgresql/tls/server.crt
sudo install -m 0644 -o postgres -g postgres /tmp/ca.crt /etc/postgresql/tls/ca.crt
sudo install -m 0600 -o postgres -g postgres /tmp/client.key /etc/postgresql/tls/client.key
sudo install -m 0644 -o postgres -g postgres /tmp/client.crt /etc/postgresql/tls/client.crt
```

Repeat the same pattern for `pgbouncer` and `redis` (adjusting owners/groups such as `redis`, `root:pgbouncer`, etc.). Once the files exist at the expected paths, enable TLS by setting the corresponding variables (for example `postgresql_ssl: true`) and run the playbooks normally.

### Example: MiaRec recorder certificates

MiaRec consumes both PostgreSQL and Redis client credentials. Copy the generated bundles:

```bash
scp certs/miarec/{client.crt,client.key,ca.crt} user@host:/tmp/
scp certs/miarec/{redis-client.crt,redis-client.key,redis-ca.crt} user@host:/tmp/
```

Install them under `/etc/miarec/tls` with the expected ownership (`root:miarec`) and permissions:

```bash
sudo install -d -m 0750 -o root -g miarec /etc/miarec/tls
sudo install -m 0640 -o root -g miarec /tmp/client.key /etc/miarec/tls/client.key
sudo install -m 0644 -o root -g miarec /tmp/client.crt /etc/miarec/tls/client.crt
sudo install -m 0644 -o root -g miarec /tmp/ca.crt /etc/miarec/tls/ca.crt
sudo install -m 0640 -o root -g miarec /tmp/redis-client.key /etc/miarec/tls/redis-client.key
sudo install -m 0644 -o root -g miarec /tmp/redis-client.crt /etc/miarec/tls/redis-client.crt
sudo install -m 0644 -o root -g miarec /tmp/redis-ca.crt /etc/miarec/tls/redis-ca.crt
```

When these files exist, `setup-miarec.yml` will automatically configure the recorder if `postgresql_ssl` or `redis_tls` are set.

### Example: MiaRec web certificates

MiaRec web needs its own client bundle plus Redis credentials. Transfer the files:

```bash
scp certs/miarecweb/{client.crt,client.key,ca.crt} user@host:/tmp/
scp certs/miarecweb/{redis-client.crt,redis-client.key,redis-ca.crt} user@host:/tmp/
```

Install them under `/etc/miarecweb/tls` (owner `root:miarec`):

```bash
sudo install -d -m 0750 -o root -g miarec /etc/miarecweb/tls
sudo install -m 0640 -o root -g miarec /tmp/client.key /etc/miarecweb/tls/client.key
sudo install -m 0644 -o root -g miarec /tmp/client.crt /etc/miarecweb/tls/client.crt
sudo install -m 0644 -o root -g miarec /tmp/ca.crt /etc/miarecweb/tls/ca.crt
sudo install -m 0640 -o root -g miarec /tmp/redis-client.key /etc/miarecweb/tls/redis-client.key
sudo install -m 0644 -o root -g miarec /tmp/redis-client.crt /etc/miarecweb/tls/redis-client.crt
sudo install -m 0644 -o root -g miarec /tmp/redis-ca.crt /etc/miarecweb/tls/redis-ca.crt
```

With these files in place, set `miarecweb_db_tls: true` / `redis_tls: true` (or rely on defaults when PostgreSQL/Redis TLS is enabled) so the playbooks wire the paths into `production.ini`.
