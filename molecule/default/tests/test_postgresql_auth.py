"""PostgreSQL authentication on the database host.

Every scenario runs these tests: default and tls on their single host, decoupled
and decoupled-tls on the database host. A local OS account must not reach the
database as the administrator without a password, over TCP or over the Unix
socket, with or without TLS. A user from postgresql_extra_users logs in with its
password only, and only over TLS when the server requires it.
"""
import os
import pytest
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('db')


def env_flag(name, default=False):
    """Return an Ansible-style boolean from the provisioner environment."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("true", "yes", "on", "1")


postgresql_version = os.environ.get('POSTGRESQL_VERSION')
# MOLECULE_INSTALL_PGBOUNCER=false skips PGBouncer
install_pgbouncer = env_flag("INSTALL_PGBOUNCER", default=True)
# The tls scenarios set TLS_ENABLED: the clients connect to PGBouncer over TLS.
# PostgreSQL itself requires TLS when the clients connect to it directly, or when
# POSTGRESQL_SSL asks for TLS between PGBouncer and PostgreSQL (tls-vars.yml).
TLS = env_flag("TLS_ENABLED")
POSTGRESQL_SSL = TLS and (env_flag("POSTGRESQL_SSL") or not install_pgbouncer)

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


def pg_hba_path(host):
    """Return pg_hba.conf from the PostgreSQL configuration directory."""
    if host.system_info.distribution == "ubuntu":
        return f"/etc/postgresql/{postgresql_version}/main/pg_hba.conf"
    return f"/etc/postgresql/{postgresql_version}/data/pg_hba.conf"


def has_ipv6_loopback(host):
    """Return True when the loopback interface has an IPv6 address."""
    inet6 = host.file("/proc/net/if_inet6")
    return inet6.exists and any(
        line.split()[-1] == "lo" for line in inet6.content_string.splitlines() if line.strip())


def is_listening(host, address, port):
    """Return True when a TCP port is bound to an address, or to the wildcard that covers it.

    testinfra does not count a wildcard socket (0.0.0.0 or ::) as listening on a
    specific address, and PGBouncer binds the wildcard in the decoupled scenarios.
    """
    wildcard = "0.0.0.0" if "." in address else "::"
    sockets = host.socket.get_listening_sockets()
    return f"tcp://{address}:{port}" in sockets or f"tcp://{wildcard}:{port}" in sockets


def run_as(host, user, command):
    """Run a command as an OS user, from a directory that every user can read."""
    if user == "root":
        return host.run(f"cd /tmp && {command}")
    return host.run("cd /tmp && su -s /bin/sh %s -c %s", user, command)


def test_pg_hba_has_no_trust_rule(host):
    """No pg_hba.conf rule accepts a connection without credentials."""
    hba = host.file(pg_hba_path(host))
    assert hba.exists, f"{hba.path} does not exist"
    rules = [line.split() for line in hba.content_string.splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    assert rules, f"{hba.path} has no rules"
    trusted = [" ".join(rule) for rule in rules if "trust" in rule]
    assert not trusted, f"{hba.path} has trust rules: {trusted}"


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
    # psql -w never prompts for a password. A missing PGPASSFILE keeps libpq from
    # reading a password file of the OS user, and libpq stays silent about it.
    result = run_as(host, os_user, f"PGPASSFILE=/nonexistent psql -w '{dsn}' -tAc 'SELECT current_user'")
    assert result.rc != 0, \
        f"{os_user} logged in as {ADMIN_USER} on {address}:{port} without a password: {result.stdout}"
    if port == 5432:
        # pg_hba.conf has no TCP rule for the administrator.
        expected = f'no pg_hba.conf entry for host "{address}", user "{ADMIN_USER}"'
    else:
        # The PGBouncer rule for local connections asks for a password.
        expected = NO_PASSWORD
    assert expected in result.stderr, f"Rejected for another reason: {result.stderr}"


def psql(host, port, sslmode, password=None):
    """Log in as the extra user on a local port and return the current user.

    psql -w never prompts for a password. Without a password, a missing
    PGPASSFILE keeps libpq from reading a password file of the OS user.
    """
    env = f"PGPASSWORD={password}" if password else "PGPASSFILE=/nonexistent"
    dsn = f"host=127.0.0.1 port={port} user={TEST_USER} dbname={TEST_DB} sslmode={sslmode} connect_timeout=5"
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
        # pgbouncer_client_tls_sslmode is require.
        expected = "SSL required"
    assert expected in result.stderr, f"Rejected for another reason: {result.stderr}"


def test_admin_socket_login_needs_os_user(host):
    """Over the Unix socket, only the postgres OS user logs in as the administrator."""
    result = run_as(host, "nobody", f"psql -w -U {ADMIN_USER} -d postgres -tAc 'SELECT 1'")
    assert result.rc != 0, f"nobody logged in as {ADMIN_USER} over the Unix socket"
    assert f'Peer authentication failed for user "{ADMIN_USER}"' in result.stderr, \
        f"Rejected for another reason: {result.stderr}"

    result = run_as(host, "postgres", "psql -w -d postgres -tAc 'SELECT 1'")
    assert result.rc == 0, f"The postgres OS user cannot log in over the Unix socket: {result.stderr}"
