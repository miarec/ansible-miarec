"""TLS private keys: an unprivileged account cannot read them.

The services that use the keys can read them: their connection tests pass.
"""
import pytest
from conftest import hosts_in, run_as, shares_host, needs_tls, INSTALL_PGBOUNCER, POSTGRESQL_SSL

testinfra_hosts = hosts_in('all')

pytestmark = needs_tls


def private_keys(host):
    """Return the private keys that the services on a host use."""
    keys = []
    if shares_host(host, "db"):
        if POSTGRESQL_SSL:
            keys.append("/etc/postgresql/tls/server.key")
        if INSTALL_PGBOUNCER:
            keys.append("/etc/pgbouncer/tls/server.key")
            if POSTGRESQL_SSL:
                keys.append("/etc/pgbouncer/tls/client.key")
    if shares_host(host, "redis"):
        keys.append("/etc/redis-tls/server.key")
    if any(shares_host(host, group) for group in ["web", "celery", "celerybeat"]):
        keys += ["/etc/miarecweb/tls/db-client.key", "/etc/miarecweb/tls/redis-client.key"]
    if shares_host(host, "recorder"):
        keys += ["/etc/miarec/tls/db-client.key", "/etc/miarec/tls/redis-client.key"]
    if shares_host(host, "screen"):
        keys += ["/etc/miarec_screen/tls/db-client.key", "/etc/miarec_screen/tls/redis-client.key"]
    return keys


def test_private_keys_are_private(host):
    keys = private_keys(host)
    if not keys:
        pytest.skip("No service on this host uses a private key")
    for key in keys:
        assert host.file(key).exists, f"{key} does not exist"
        result = run_as(host, "nobody", f"cat {key}")
        assert result.rc != 0, f"The nobody account can read {key}"
