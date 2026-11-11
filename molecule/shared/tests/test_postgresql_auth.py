"""PostgreSQL authentication on the database host.

A local OS account must not reach the database as the administrator without a
password, over TCP or over the Unix socket, with or without TLS. A user from
postgresql_extra_users logs in with its password only, only over TLS when the
server requires it, and only with a client certificate when the server requires
one (DB_CLIENTCERT).
"""
import pytest
from conftest import hosts_in, is_listening, run_as, \
    TLS, INSTALL_PGBOUNCER, POSTGRESQL_SSL, DB_CLIENTCERT, TEST_CLIENT_CERT

testinfra_hosts = hosts_in('db')

install_pgbouncer = INSTALL_PGBOUNCER

ADMIN_USER = "postgres"
# The extra user that molecule/shared/install-vars.yml creates
TEST_USER = "testuser"
TEST_PASSWORD = "testpassword"
TEST_DB = "testdb"
# libpq reports a password request that psql -w cannot answer with this error.
NO_PASSWORD = "fe_sendauth: no password supplied"

# (address, port, required): the TCP endpoints of PostgreSQL and PGBouncer on the
# database host. A required endpoint must listen; PostgreSQL listens on ::1 only
# when the container has IPv6 on the loopback interface.
ENDPOINTS = [("127.0.0.1", 5432, True), ("::1", 5432, False)]
if install_pgbouncer:
    ENDPOINTS.append(("127.0.0.1", 6432, True))

# (port, tls): the endpoints that the extra user connects to, and whether the
# endpoint requires TLS.
USER_ENDPOINTS = [(5432, POSTGRESQL_SSL)]
if install_pgbouncer:
    USER_ENDPOINTS.append((6432, TLS))


def has_ipv6_loopback(host):
    """Return True when the loopback interface has an IPv6 address."""
    inet6 = host.file("/proc/net/if_inet6")
    return inet6.exists and any(
        line.split()[-1] == "lo" for line in inet6.content_string.splitlines() if line.strip())


@pytest.mark.parametrize("os_user", ["root", "nobody"])
@pytest.mark.parametrize("address,port,required", ENDPOINTS)
def test_admin_tcp_login_needs_password(host, os_user, address, port, required):
    """The administrator cannot log in over TCP without a password.

    sslmode=prefer tries TLS first and falls back to plaintext, so the test covers
    hostssl and host rules alike.
    """
    if address == "::1" and not has_ipv6_loopback(host):
        pytest.skip("The loopback interface has no IPv6 address")
    if not is_listening(host, address, port):
        assert not required, f"Nothing listens on {address}:{port}"
        pytest.skip(f"Nothing listens on {address}:{port}")
    dsn = f"host={address} port={port} user={ADMIN_USER} dbname=postgres sslmode=prefer connect_timeout=5"
    # With DB_CLIENTCERT, root presents the trusted test client certificate, so the
    # test proves that the certificate alone does not log the administrator in.
    # Only root can read its private key.
    with_cert = DB_CLIENTCERT and os_user == "root"
    if with_cert:
        dsn += f" sslcert={TEST_CLIENT_CERT}.crt sslkey={TEST_CLIENT_CERT}.key"
    # psql -w never prompts for a password. A missing PGPASSFILE keeps libpq from
    # reading a password file of the OS user, and libpq stays silent about it.
    result = run_as(host, os_user, f"PGPASSFILE=/nonexistent psql -w '{dsn}' -tAc 'SELECT current_user'")
    assert result.rc != 0, \
        f"{os_user} logged in as {ADMIN_USER} on {address}:{port} without a password: {result.stdout}"
    if port == 5432:
        # pg_hba.conf has no TCP rule for the administrator.
        expected = f'no pg_hba.conf entry for host "{address}", user "{ADMIN_USER}"'
    elif DB_CLIENTCERT and not with_cert:
        # PGBouncer's client_tls_sslmode=verify-ca ends the TLS handshake of a
        # client without a certificate, before any password request.
        expected = "SSL error"
    else:
        # The PGBouncer rule for local connections asks for a password.
        expected = NO_PASSWORD
    assert expected in result.stderr, f"Rejected for another reason: {result.stderr}"


def psql(host, port, sslmode, password=None, client_cert=DB_CLIENTCERT):
    """Log in as the extra user on a local port and return the current user.

    psql -w never prompts for a password. Without a password, a missing
    PGPASSFILE keeps libpq from reading a password file of the OS user. With
    client_cert, presents the trusted test client certificate, which the
    endpoints demand when the scenario requires client certificates.
    """
    env = f"PGPASSWORD={password}" if password else "PGPASSFILE=/nonexistent"
    dsn = f"host=127.0.0.1 port={port} user={TEST_USER} dbname={TEST_DB} sslmode={sslmode} connect_timeout=5"
    if client_cert:
        dsn += f" sslcert={TEST_CLIENT_CERT}.crt sslkey={TEST_CLIENT_CERT}.key"
    return host.run(f"{env} psql -w '{dsn}' -tAc 'SELECT current_user'")


@pytest.mark.parametrize("port,tls", USER_ENDPOINTS)
def test_extra_user_logs_in_with_password(host, port, tls):
    """A user from postgresql_extra_users logs in with its password.

    sslmode=prefer uses TLS when the server offers it.
    """
    result = psql(host, port, "prefer", TEST_PASSWORD)
    assert result.rc == 0, f"{TEST_USER} cannot log in on port {port}: {result.stderr}"
    assert result.stdout.strip() == TEST_USER


@pytest.mark.parametrize("password", [None, "wrong"], ids=["no-password", "wrong-password"])
@pytest.mark.parametrize("port,tls", USER_ENDPOINTS)
def test_extra_user_needs_password(host, port, tls, password):
    """A user from postgresql_extra_users cannot log in without its password."""
    result = psql(host, port, "prefer", password)
    assert result.rc != 0, f"{TEST_USER} logged in on port {port} without its password: {result.stdout}"
    if password is None:
        expected = NO_PASSWORD
    elif port == 5432:
        expected = f'password authentication failed for user "{TEST_USER}"'
    else:
        # PGBouncer does not name the user.
        expected = "password authentication failed"
    assert expected in result.stderr, f"Rejected for another reason: {result.stderr}"


@pytest.mark.parametrize("port,tls", USER_ENDPOINTS)
def test_extra_user_plaintext_login(host, port, tls):
    """An endpoint that requires TLS rejects a plaintext login, even with the password."""
    result = psql(host, port, "disable", TEST_PASSWORD)
    if not tls:
        assert result.rc == 0, f"Port {port} rejected a plaintext login without TLS: {result.stderr}"
        return
    assert result.rc != 0, f"Port {port} accepted a plaintext login although it requires TLS: {result.stdout}"
    if port == 5432:
        # Only hostssl rules match, so PostgreSQL finds no rule for the connection.
        expected = (f'no pg_hba.conf entry for host "127.0.0.1", user "{TEST_USER}", '
                    f'database "{TEST_DB}", no encryption')
    else:
        # pgbouncer_client_tls_sslmode is require or verify-ca.
        expected = "SSL required"
    assert expected in result.stderr, f"Rejected for another reason: {result.stderr}"


@pytest.mark.parametrize("port,tls", USER_ENDPOINTS)
def test_extra_user_login_without_client_certificate(host, port, tls):
    """An endpoint requires a client certificate exactly when the scenario asks for it.

    With DB_CLIENTCERT, the password alone is refused on the TLS endpoints:
    PostgreSQL by the clientcert option of its hostssl rules, PGBouncer by
    client_tls_sslmode=verify-ca during the TLS handshake. Without it, the
    password alone logs in.
    """
    if not tls:
        pytest.skip(f"Port {port} does not use TLS")
    result = psql(host, port, "require", TEST_PASSWORD, client_cert=False)
    if not DB_CLIENTCERT:
        assert result.rc == 0, f"Port {port} rejected a login without a client certificate: {result.stderr}"
        return
    assert result.rc != 0, f"Port {port} accepted a login without a client certificate: {result.stdout}"
    if port == 5432:
        expected = "connection requires a valid client certificate"
    else:
        # The TLS alert differs between TLS versions, so check only that the
        # handshake failed.
        expected = "SSL error"
    assert expected in result.stderr, f"Rejected for another reason: {result.stderr}"


def test_admin_socket_login_needs_os_user(host):
    """Over the Unix socket, only the postgres OS user logs in as the administrator."""
    result = run_as(host, "nobody", f"psql -w -U {ADMIN_USER} -d postgres -tAc 'SELECT 1'")
    assert result.rc != 0, f"nobody logged in as {ADMIN_USER} over the Unix socket"
    assert f'Peer authentication failed for user "{ADMIN_USER}"' in result.stderr, \
        f"Rejected for another reason: {result.stderr}"

    result = run_as(host, "postgres", "psql -w -d postgres -tAc 'SELECT 1'")
    assert result.rc == 0, f"The postgres OS user cannot log in over the Unix socket: {result.stderr}"
