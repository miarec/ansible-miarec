"""Database tier: PostgreSQL and, unless MOLECULE_INSTALL_PGBOUNCER=false, PGBouncer.

The connection tests run the client on a MiaRec Web host, with the client
certificates that MiaRec Web uses. The applications connect to the same port.
"""
import pytest
from conftest import (
    hosts_in, shares_host, has_remote_clients, is_listening, listening_on_all_interfaces,
    postgresql_service, miarecweb_client, db_query, db_rows, needs_tls,
    TLS, INSTALL_PGBOUNCER, POSTGRESQL_SSL, PGBOUNCER_PORT, POSTGRESQL_PORT, REDIS_PORT, UNTRUSTED_CERT,
)

testinfra_hosts = hosts_in('db')


def test_service(host):
    services = [postgresql_service(host)]
    if INSTALL_PGBOUNCER:
        services.append("pgbouncer")
    for service in services:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_listening(host):
    """The port that the applications use is open to other hosts only when they need it.

    Behind PGBouncer, PostgreSQL stays on the loopback interface.
    """
    app_port = PGBOUNCER_PORT if INSTALL_PGBOUNCER else POSTGRESQL_PORT
    assert is_listening(host, "127.0.0.1", POSTGRESQL_PORT), "PostgreSQL does not listen on 127.0.0.1"
    if INSTALL_PGBOUNCER:
        assert not listening_on_all_interfaces(host, POSTGRESQL_PORT), \
            "PostgreSQL must not listen on all interfaces behind PGBouncer"
    else:
        assert not host.socket(f"tcp://127.0.0.1:{PGBOUNCER_PORT}").is_listening, "PGBouncer must not run"
    if has_remote_clients(host):
        assert listening_on_all_interfaces(host, app_port), f"Port {app_port} is not open to the other hosts"
    else:
        assert is_listening(host, "127.0.0.1", app_port), f"Nothing listens on 127.0.0.1:{app_port}"
        assert not listening_on_all_interfaces(host, app_port), \
            f"Port {app_port} must not listen on all interfaces without remote clients"


def test_client_connects():
    """A MiaRec Web host logs in with the application credentials and its client certificate."""
    result = db_query(miarecweb_client(), "SELECT 1 AS one")
    assert result.rc == 0, f"Database connection failed: {result.stderr}"


def test_postgresql_transport():
    """The connection to PostgreSQL itself uses TLS only when PostgreSQL has TLS on.

    Behind PGBouncer, this is the connection from PGBouncer to PostgreSQL.
    """
    rows = db_rows(miarecweb_client(), "SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
    assert rows == [{"ssl": POSTGRESQL_SSL}]


def test_plaintext_login():
    """With TLS, the database tier rejects a plaintext login, even with the right password."""
    result = db_query(miarecweb_client(), "SELECT 1", tls=False)
    if TLS:
        assert result.rc != 0, "The database tier accepted a login without TLS"
    else:
        assert result.rc == 0, f"The database tier rejected a plaintext login: {result.stderr}"


@needs_tls
def test_rejects_untrusted_client_certificate():
    """The database tier rejects a client certificate that its CA did not sign."""
    result = db_query(miarecweb_client(), "SELECT 1", client_cert=UNTRUSTED_CERT)
    assert result.rc != 0, "The database tier accepted an untrusted client certificate"
    # The server ends the TLS handshake with an alert. A password error would mean
    # that it accepted the certificate.
    assert "SSL error" in result.stderr and "alert" in result.stderr, f"Rejected for another reason: {result.stderr}"


@needs_tls
def test_server_certificate_needs_the_client_ca():
    """A client that trusts another CA rejects the server certificate.

    So test_client_connects passes only because the CA of MiaRec Web signed the
    server certificate.
    """
    result = db_query(miarecweb_client(), "SELECT 1", ca_file=f"{UNTRUSTED_CERT}.crt")
    assert result.rc != 0, "The client accepted a server certificate that its CA did not sign"
    assert "certificate verify failed" in result.stderr, f"Rejected for another reason: {result.stderr}"


def test_no_redis(host):
    """Redis runs on its own host in the decoupled scenarios."""
    if shares_host(host, "redis"):
        pytest.skip("Redis runs on this host")
    assert not host.socket(f"tcp://127.0.0.1:{REDIS_PORT}").is_listening
    assert not listening_on_all_interfaces(host, REDIS_PORT)
    assert not host.exists("redis-server"), "Redis must not be installed on the database host"


def test_no_application(host):
    """The database host carries no application in the decoupled scenarios."""
    if any(shares_host(host, group) for group in ["web", "celery", "recorder", "screen"]):
        pytest.skip("An application runs on this host")
    for comm in ["miarec", "miarec_screen", "celery", "miarec_livemon"]:
        assert host.run("ps -C %s", comm).rc != 0, f"{comm} must not run on the database host"
