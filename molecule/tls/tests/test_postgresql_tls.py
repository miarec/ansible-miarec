import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

postgresql_version = os.environ.get('POSTGRESQL_VERSION')


def test_postgresql_service_running(host):
    """Verify PostgreSQL service is enabled and running."""
    if host.system_info.distribution == "ubuntu":
        s = host.service("postgresql")
    else:
        s = host.service("postgresql-{}".format(postgresql_version))
    assert s.is_enabled
    assert s.is_running


def test_postgresql_port_listening(host):
    """Verify PostgreSQL is listening on port 5432."""
    s = host.socket("tcp://127.0.0.1:5432")
    assert s.is_listening


def test_postgresql_ssl_enabled(host):
    """Verify PostgreSQL has SSL enabled in configuration."""
    if host.system_info.distribution == "ubuntu":
        conf_path = "/etc/postgresql/{}/main/postgresql.conf".format(
            postgresql_version)
    else:
        conf_path = "/etc/postgresql/{}/data/postgresql.conf".format(
            postgresql_version)

    conf = host.file(conf_path)
    assert conf.exists
    assert conf.contains("ssl = on")


def test_postgresql_tls_connection_with_sslmode_require(host):
    """Verify PostgreSQL accepts TLS connections with sslmode=require."""
    cmd = host.run(
        'psql "host=127.0.0.1 user=postgres dbname=postgres sslmode=require" '
        "-c 'SELECT 1;'"
    )
    assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


def test_postgresql_tls_connection_with_verify_ca(host):
    """Verify PostgreSQL accepts TLS connections with CA verification."""
    cmd = host.run(
        'psql "host=127.0.0.1 user=postgres dbname=postgres '
        'sslmode=verify-ca sslrootcert=/etc/postgresql/tls/ca.crt" '
        "-c 'SELECT 1;'"
    )
    assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


def test_postgresql_tls_connection_with_client_cert(host):
    """Verify PostgreSQL accepts TLS connections with client certificates."""
    cmd = host.run(
        'psql "host=127.0.0.1 user=postgres dbname=postgres '
        'sslmode=verify-ca '
        'sslrootcert=/etc/miarecweb/tls/ca.crt '
        'sslcert=/etc/miarecweb/tls/client.crt '
        'sslkey=/etc/miarecweb/tls/client.key" '
        "-c 'SELECT 1;'"
    )
    assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"

# def test_postgresql_ssl_connection_with_sslmode_require(host):
#     """Verify PostgreSQL accepts TLS connections with sslmode=require."""
#     cmd = host.run(
#         'psql "host=127.0.0.1 user=postgres dbname=postgres '
#         'sslmode=require '
#         'sslcert=/etc/miarecweb/tls/client.crt '
#         'sslkey=/etc/miarecweb/tls/client.key" '
#         "-c 'SELECT 1;'"
#     )
#     assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


# def test_postgresql_ssl_connection_with_verify_ca(host):
#     """Verify PostgreSQL accepts TLS connections with CA verification."""
#     cmd = host.run(
#         'psql "host=127.0.0.1 user=postgres dbname=postgres '
#         'sslmode=verify-ca '
#         'sslrootcert=/etc/miarecweb/tls/ca.crt '
#         'sslcert=/etc/miarecweb/tls/client.crt '
#         'sslkey=/etc/miarecweb/tls/client.key" '
#         "-c 'SELECT 1;'"
#     )
#     assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


# def test_postgresql_ssl_connection_with_client_cert(host):
#     """Verify PostgreSQL accepts TLS connections with client certificates."""
#     cmd = host.run(
#         'psql "host=127.0.0.1 user=postgres dbname=postgres '
#         'sslmode=verify-ca '
#         'sslrootcert=/etc/miarecweb/tls/ca.crt '
#         'sslcert=/etc/miarecweb/tls/client.crt '
#         'sslkey=/etc/miarecweb/tls/client.key" '
#         "-c 'SELECT 1;'"
#     )
#     assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


def test_postgresql_ssl_info_in_connection(host):
    """Verify SSL is actually being used in the connection."""
    cmd = host.run(
        'psql "host=127.0.0.1 user=postgres dbname=postgres sslmode=require" '
        "-c 'SHOW ssl;'"
    )
    assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"
    assert "on" in cmd.stdout


def test_postgresql_connection_without_tls_fails(host):
    """Verify PostgreSQL rejects non-TLS connections (hostssl only in pg_hba)."""
    cmd = host.run(
        'psql "host=127.0.0.1 user=postgres dbname=postgres sslmode=disable" '
        "-c 'SELECT 1;'"
    )
    # Connection should fail when TLS is required via hostssl-only pg_hba config
    assert cmd.rc != 0, "Connection without TLS should be rejected"
