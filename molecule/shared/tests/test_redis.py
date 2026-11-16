"""Redis tier.

The connection tests run the client on a MiaRec Web host, with the client
certificate that MiaRec Web uses.
"""
import pytest
from conftest import (
    hosts_in, shares_host, has_remote_clients, is_listening, listening_on_all_interfaces,
    redis_service, miarecweb_client, redis_ping, needs_tls,
    TLS, PGBOUNCER_PORT, POSTGRESQL_PORT, REDIS_PORT, UNTRUSTED_CERT,
)

testinfra_hosts = hosts_in('redis')


def test_service(host):
    service = redis_service(host)
    s = host.service(service)
    assert s.is_enabled, f"Service {service} is not enabled"
    assert s.is_running, f"Service {service} is not running"


def test_listening(host):
    """Redis is open to other hosts only when they need it."""
    if has_remote_clients(host):
        assert listening_on_all_interfaces(host, REDIS_PORT), "Redis is not open to the other hosts"
    else:
        assert is_listening(host, "127.0.0.1", REDIS_PORT), f"Nothing listens on 127.0.0.1:{REDIS_PORT}"
        assert not listening_on_all_interfaces(host, REDIS_PORT), \
            "Redis must not listen on all interfaces without remote clients"


def test_client_connects():
    """A MiaRec Web host sends PING, over TLS with its client certificate in the TLS scenarios."""
    result = redis_ping(miarecweb_client())
    assert result.rc == 0, f"Redis connection failed: {result.stderr}"
    assert result.stdout.strip() == "True"


def test_plaintext_connection():
    """With TLS, Redis rejects a plaintext connection."""
    result = redis_ping(miarecweb_client(), tls=False)
    if TLS:
        assert result.rc != 0, "Redis accepted a connection without TLS"
    else:
        assert result.rc == 0, f"Redis rejected a plaintext connection: {result.stderr}"


@needs_tls
def test_rejects_untrusted_client_certificate():
    result = redis_ping(miarecweb_client(), client_cert=UNTRUSTED_CERT)
    assert result.rc != 0, "Redis accepted a client certificate that its CA did not sign"


@needs_tls
def test_requires_client_certificate():
    result = redis_ping(miarecweb_client(), client_cert=None)
    assert result.rc != 0, "Redis accepted a TLS connection without a client certificate"


@needs_tls
def test_server_certificate_needs_the_client_ca():
    """A client that trusts another CA rejects the server certificate.

    So test_client_connects passes only because the CA of MiaRec Web signed the
    server certificate.
    """
    result = redis_ping(miarecweb_client(), ca_file=f"{UNTRUSTED_CERT}.crt")
    assert result.rc != 0, "The client accepted a server certificate that its CA did not sign"
    assert "certificate verify failed" in result.stderr, f"Rejected for another reason: {result.stderr}"


def test_no_database(host):
    """PostgreSQL and PGBouncer run on the database host in the decoupled scenarios."""
    if shares_host(host, "db"):
        pytest.skip("The database runs on this host")
    assert not host.socket(f"tcp://127.0.0.1:{POSTGRESQL_PORT}").is_listening
    assert not listening_on_all_interfaces(host, PGBOUNCER_PORT)


def test_no_application(host):
    """The Redis host carries no application in the decoupled scenarios."""
    if any(shares_host(host, group) for group in ["web", "celery", "recorder", "screen"]):
        pytest.skip("An application runs on this host")
    for comm in ["miarec", "miarec_screen", "celery", "miarec_livemon"]:
        assert host.run("ps -C %s", comm).rc != 0, f"{comm} must not run on the Redis host"
