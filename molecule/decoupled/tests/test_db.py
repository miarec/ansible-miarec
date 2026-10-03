"""Database tier: PostgreSQL and PGBouncer on one host. No Redis."""
import os
from conftest import hosts_in, peer_ip, own_ip, listening_on_all_interfaces, PGBOUNCER_PORT, REDIS_PORT

testinfra_hosts = hosts_in('db')

postgresql_version = os.environ.get('POSTGRESQL_VERSION')


def test_directories(host):
    if host.system_info.distribution == "ubuntu":
        postgresql_dir = "/etc/postgresql/{}".format(postgresql_version)
    else:
        postgresql_dir = "/var/lib/pgsql/{}/data".format(postgresql_version)

    for dir in [postgresql_dir, "/var/log/pgbouncer"]:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_service(host):
    if host.system_info.distribution == "ubuntu":
        services = ["postgresql", "pgbouncer"]
    else:
        services = ["postgresql-{}".format(postgresql_version), "pgbouncer"]

    for service in services:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_socket(host):
    # PostgreSQL stays private: PGBouncer is the only client.
    assert host.socket("tcp://127.0.0.1:5432").is_listening
    assert not listening_on_all_interfaces(host, 5432), "PostgreSQL must not listen on all interfaces behind PGBouncer"
    # PGBouncer serves the other tiers.
    assert listening_on_all_interfaces(host, PGBOUNCER_PORT), "PGBouncer does not listen on all interfaces"


def test_pgbouncer_hba_allows_peers(host):
    """Every tier that uses the database has a PGBouncer hba rule."""
    hba = host.file("/etc/pgbouncer/pgbouncer_hba.conf")
    assert hba.exists
    me = own_ip(host)
    for group in ["web", "celery", "recorder", "screen"]:
        ip = peer_ip(host, group)
        assert ip != me
        assert f"{ip}/32" in hba.content_string, f"No pgbouncer hba rule for {group} host {ip}"


def test_no_redis(host):
    """Redis runs on its own host."""
    assert not host.socket(f"tcp://127.0.0.1:{REDIS_PORT}").is_listening
    assert not listening_on_all_interfaces(host, REDIS_PORT)
    assert not host.exists("redis-server"), "Redis must not be installed on the database host"


def test_no_application_tiers(host):
    """The database host carries no application."""
    for path in ["/opt/miarecweb", "/opt/miarec", "/opt/miarec_screen"]:
        assert not host.file(path).exists, f"{path} must not exist on the database host"
