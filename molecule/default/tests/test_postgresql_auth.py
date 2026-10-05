"""PostgreSQL authentication on the database host.

Every scenario runs these tests: default and tls on their single host, decoupled
and decoupled-tls on the database host. A local OS account must not reach the
database as the administrator without a password, over TCP or over the Unix
socket, with or without TLS.
"""
import os
import pytest
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('db')

postgresql_version = os.environ.get('POSTGRESQL_VERSION')
# MOLECULE_INSTALL_PGBOUNCER=false skips PGBouncer
install_pgbouncer = os.environ.get('INSTALL_PGBOUNCER', 'true').lower() in ('true', 'yes', '1')

ADMIN_USER = "postgres"
# Errors that show the server refused the login, as opposed to a connection that
# never reached it. PGBouncer reports a missing hba rule as "no authentication
# method is found".
AUTH_ERRORS = ("no pg_hba.conf entry", "no authentication method", "password", "authentication failed")

# (address, port, required): the TCP endpoints of PostgreSQL and PGBouncer on the
# database host. A required endpoint must listen; PostgreSQL listens on ::1 only
# when the container has IPv6 on the loopback interface.
ENDPOINTS = [("127.0.0.1", 5432, True), ("::1", 5432, False)]
if install_pgbouncer:
    ENDPOINTS.append(("127.0.0.1", 6432, True))


def pg_hba_path(host):
    """Return pg_hba.conf from the PostgreSQL configuration directory."""
    if host.system_info.distribution == "ubuntu":
        return f"/etc/postgresql/{postgresql_version}/main/pg_hba.conf"
    return f"/etc/postgresql/{postgresql_version}/data/pg_hba.conf"


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
    if not host.socket(f"tcp://{address}:{port}").is_listening:
        assert not required, f"Nothing listens on {address}:{port}"
        pytest.skip(f"Nothing listens on {address}:{port}")
    dsn = f"host={address} port={port} user={ADMIN_USER} dbname=postgres sslmode=prefer connect_timeout=5"
    result = run_as(host, os_user, f"PGPASSFILE=/dev/null psql -w '{dsn}' -tAc 'SELECT current_user'")
    assert result.rc != 0, \
        f"{os_user} logged in as {ADMIN_USER} on {address}:{port} without a password: {result.stdout}"
    assert any(error in result.stderr for error in AUTH_ERRORS), \
        f"The connection failed before authentication: {result.stderr}"


def test_admin_socket_login_needs_os_user(host):
    """Over the Unix socket, only the postgres OS user logs in as the administrator."""
    result = run_as(host, "nobody", f"psql -w -U {ADMIN_USER} -d postgres -tAc 'SELECT 1'")
    assert result.rc != 0, f"nobody logged in as {ADMIN_USER} over the Unix socket"
    assert "authentication failed" in result.stderr, \
        f"The connection failed before authentication: {result.stderr}"

    result = run_as(host, "postgres", "psql -w -d postgres -tAc 'SELECT 1'")
    assert result.rc == 0, f"The postgres OS user cannot log in over the Unix socket: {result.stderr}"
