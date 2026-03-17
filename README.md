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

Repeat the same pattern for `pgbouncer`, `redis`, `miarec`, and `miarecweb` (adjusting owners/groups such as `redis`, `root:miarec`, etc.). Once the files exist at the expected paths, enable TLS by setting the corresponding variables (for example `postgresql_ssl: true`) and run the playbooks normally.
