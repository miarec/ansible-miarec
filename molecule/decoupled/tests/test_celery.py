"""Celery tier: worker and beat. No Apache.

The Celery host has the MiaRec Web client certificates and Python, so the
tests here also check the database and Redis transports over the network.
"""
import os
import pytest
from conftest import (
    hosts_in, peer_ip, process_owners, db_query, redis_ping,
    TLS, POSTGRESQL_SSL, UNTRUSTED_TLS_DIR,
)

testinfra_hosts = hosts_in('celery')

miarecweb_version = os.environ.get('MIARECWEB_VERSION')


def test_directories(host):
    for dir in [
        "/opt/miarecweb/releases/{}".format(miarecweb_version),
        "/var/log/miarecweb",
        "/var/log/miarecweb/celery",
    ]:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_files(host):
    for file in [
        "/etc/systemd/system/celerybeat.service",
        "/etc/systemd/system/celeryd.service",
        "/var/log/miarecweb/celery/beat.log",
        "/var/log/miarecweb/celery/worker1.log",
    ]:
        f = host.file(file)
        assert f.exists and f.is_file, f"File {file} does not exist"


def test_service(host):
    for service in ["celeryd", "celerybeat"]:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_process_user(host):
    """The Celery worker and beat run as the celery user in the miarec group."""
    assert process_owners(host, "celery") == {("celery", "miarec")}


def test_no_apache(host):
    apache = "apache2" if host.system_info.distribution == "ubuntu" else "httpd"
    assert not host.exists(apache), f"{apache} must not be installed on the Celery host"
    assert not host.socket("tcp://0.0.0.0:80").is_listening


def test_production_ini_points_to_peers(host):
    ini = host.file("/opt/miarecweb/releases/{}/production.ini".format(miarecweb_version))
    assert ini.exists
    db_ip = peer_ip(host, 'db')
    redis_ip = peer_ip(host, 'redis')
    assert ini.contains(f"^DATABASE_HOST = {db_ip}$")
    assert ini.contains(f"^REDIS_HOST = {redis_ip}$")


def test_database_connection(host):
    """The Celery host authenticates against the database tier, over TLS in decoupled-tls."""
    result = db_query(host, "SELECT 1")
    assert result.rc == 0, f"Database connection failed: {result.stderr}"
    assert result.stdout.strip() == "1"


def test_postgresql_transport(host):
    """The connection to PostgreSQL itself uses TLS only when PostgreSQL has TLS on.

    Behind PGBouncer, this is the connection from PGBouncer to PostgreSQL.
    """
    result = db_query(host, "SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
    assert result.rc == 0, f"Database connection failed: {result.stderr}"
    assert result.stdout.strip() == str(POSTGRESQL_SSL)


@pytest.mark.skipif(not TLS, reason="TLS is off")
def test_database_rejects_plaintext(host):
    result = db_query(host, "SELECT 1", tls=False)
    assert result.rc != 0, "The database tier accepted a connection without TLS"


def test_redis_connection(host):
    """The Celery host reaches Redis on the Redis host, over TLS in decoupled-tls."""
    result = redis_ping(host)
    assert result.rc == 0, f"Redis connection failed: {result.stderr}"
    assert result.stdout.strip() == "True"


@pytest.mark.skipif(not TLS, reason="TLS is off")
def test_redis_rejects_plaintext(host):
    result = redis_ping(host, tls=False)
    assert result.rc != 0, "Redis accepted a connection without TLS"


@pytest.mark.skipif(not TLS, reason="TLS is off")
def test_redis_rejects_untrusted_client(host):
    # Make sure that the test does not pass only because the fixture is missing.
    assert host.file(f"{UNTRUSTED_TLS_DIR}/client.crt").exists
    result = redis_ping(host, client_cert=f"{UNTRUSTED_TLS_DIR}/client")
    assert result.rc != 0, "Redis accepted a client certificate that its CA did not sign"
