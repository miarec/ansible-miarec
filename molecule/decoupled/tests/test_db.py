"""Database tier: PostgreSQL and, unless MOLECULE_INSTALL_PGBOUNCER=false, PGBouncer. No Redis."""
import pytest
from conftest import (
    hosts_in, peer_ip, own_ip, listening_on_all_interfaces, postgresql_paths,
    TLS, INSTALL_PGBOUNCER, POSTGRESQL_SSL, PGBOUNCER_PORT, POSTGRESQL_PORT, REDIS_PORT,
)

testinfra_hosts = hosts_in('db')

needs_pgbouncer = pytest.mark.skipif(not INSTALL_PGBOUNCER, reason="PGBouncer is not installed")


def test_directories(host):
    postgresql_dir, _ = postgresql_paths(host)
    dirs = [postgresql_dir]
    if INSTALL_PGBOUNCER:
        dirs.append("/var/log/pgbouncer")
    for dir in dirs:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_service(host):
    _, postgresql_service = postgresql_paths(host)
    services = [postgresql_service]
    if INSTALL_PGBOUNCER:
        services.append("pgbouncer")
    for service in services:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_socket(host):
    if INSTALL_PGBOUNCER:
        # PostgreSQL stays private: PGBouncer is the only client.
        assert host.socket(f"tcp://127.0.0.1:{POSTGRESQL_PORT}").is_listening
        assert not listening_on_all_interfaces(host, POSTGRESQL_PORT), \
            "PostgreSQL must not listen on all interfaces behind PGBouncer"
        # PGBouncer serves the other tiers.
        assert listening_on_all_interfaces(host, PGBOUNCER_PORT), "PGBouncer does not listen on all interfaces"
    else:
        # The other tiers connect to PostgreSQL directly.
        assert listening_on_all_interfaces(host, POSTGRESQL_PORT), "PostgreSQL does not listen on all interfaces"
        assert not host.file("/etc/pgbouncer/pgbouncer.ini").exists, "PGBouncer must not be installed"


def test_postgresql_query(host):
    """PostgreSQL accepts connections and answers queries."""
    result = host.run("sudo -u postgres psql -tAc 'SELECT 1;'")
    assert result.rc == 0, f"psql failed: {result.stderr}"
    assert result.stdout.strip() == "1", f"Unexpected reply: {result.stdout}"


def test_hba_allows_peers(host):
    """Every tier that uses the database has an hba rule on the server it connects to.

    With TLS, the rules accept TLS connections only (hostssl).
    """
    if INSTALL_PGBOUNCER:
        hba_path = "/etc/pgbouncer/pgbouncer_hba.conf"
    else:
        hba_path = "{}/pg_hba.conf".format(postgresql_paths(host)[0])
    hba = host.file(hba_path)
    assert hba.exists, f"{hba_path} does not exist"
    rules = [line.split() for line in hba.content_string.splitlines() if line.strip() and not line.startswith("#")]
    expected_type = "hostssl" if TLS else "host"
    me = own_ip(host)
    for group in ["web", "celery", "recorder", "screen"]:
        ip = peer_ip(host, group)
        assert ip != me
        types = {rule[0] for rule in rules if f"{ip}/32" in rule}
        assert types, f"No rule for {group} host {ip} in {hba_path}"
        assert types == {expected_type}, f"Rules for {group} host {ip} in {hba_path} have types {types}, expected {expected_type}"


def test_postgresql_ssl(host):
    """PostgreSQL turns on TLS only when its clients need it.

    Behind PGBouncer on the same host, TLS stays off unless
    MOLECULE_POSTGRESQL_SSL=true asks for it.
    """
    result = host.run("sudo -u postgres psql -tAc 'SHOW ssl;'")
    assert result.rc == 0, f"psql failed: {result.stderr}"
    assert result.stdout.strip() == ("on" if POSTGRESQL_SSL else "off")


@needs_pgbouncer
def test_pgbouncer_tls_config(host):
    """PGBouncer requires TLS from clients, and uses TLS to PostgreSQL when PostgreSQL has it."""
    conf = host.file("/etc/pgbouncer/pgbouncer.ini")
    assert conf.exists
    assert conf.contains("^client_tls_sslmode = require$") == TLS
    assert conf.contains("^server_tls_sslmode = ") == POSTGRESQL_SSL


def test_no_redis(host):
    """Redis runs on its own host."""
    assert not host.socket(f"tcp://127.0.0.1:{REDIS_PORT}").is_listening
    assert not listening_on_all_interfaces(host, REDIS_PORT)
    assert not host.exists("redis-server"), "Redis must not be installed on the database host"


def test_no_application_tiers(host):
    """The database host carries no application."""
    for path in ["/opt/miarecweb", "/opt/miarec", "/opt/miarec_screen"]:
        assert not host.file(path).exists, f"{path} must not exist on the database host"
