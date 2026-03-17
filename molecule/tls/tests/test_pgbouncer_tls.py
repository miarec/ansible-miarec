# import os
# import testinfra.utils.ansible_runner

# testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
#     os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')


# def test_pgbouncer_service_running(host):
#     """Verify PGBouncer service is enabled and running."""
#     s = host.service("pgbouncer")
#     assert s.is_enabled
#     assert s.is_running


# def test_postgresql_service_running(host):
#     """Verify PostgreSQL service is enabled and running."""
#     s = host.service("postgresql")
#     assert s.is_enabled
#     assert s.is_running


# def test_pgbouncer_port_listening(host):
#     """Verify PGBouncer is listening on port 6432."""
#     s = host.socket("tcp://0.0.0.0:6432")
#     assert s.is_listening


# def test_postgresql_ssl_enabled(host):
#     """Verify PostgreSQL has SSL enabled."""
#     # Check via SHOW ssl command
#     cmd = host.run("sudo -u postgres psql -c 'SHOW ssl;' -t -A")
#     assert cmd.rc == 0, f"Failed to check SSL: {cmd.stderr}"
#     assert "on" in cmd.stdout


# def test_pgbouncer_client_tls_config(host):
#     """Verify PGBouncer client TLS configuration is present."""
#     conf = host.file("/etc/pgbouncer/pgbouncer.ini")
#     assert conf.exists
#     assert conf.contains("client_tls_sslmode = require")
#     assert conf.contains("client_tls_key_file = /etc/pgbouncer/tls/server.key")
#     assert conf.contains("client_tls_cert_file = /etc/pgbouncer/tls/server.crt")


# def test_pgbouncer_server_tls_config(host):
#     """Verify PGBouncer server TLS configuration is present."""
#     conf = host.file("/etc/pgbouncer/pgbouncer.ini")
#     assert conf.exists
#     assert conf.contains("server_tls_sslmode = require")
#     assert conf.contains("server_tls_ca_file = /etc/pgbouncer/tls/ca.crt")


# def test_tls_certificates_exist(host):
#     """Verify TLS certificates are properly created."""
#     pgbouncer_files = [
#         "/etc/pgbouncer/tls/ca.crt",
#         "/etc/pgbouncer/tls/server.crt",
#         "/etc/pgbouncer/tls/server.key"
#     ]
#     postgresql_files = [
#         "/etc/postgresql/tls/ca.crt",
#         "/etc/postgresql/tls/server.crt",
#         "/etc/postgresql/tls/server.key"
#     ]
#     for f in pgbouncer_files + postgresql_files:
#         cert = host.file(f)
#         assert cert.exists, f"Certificate file {f} does not exist"


# def test_pgbouncer_tls_connection_with_sslmode_require(host):
#     """Verify PGBouncer accepts TLS connections with sslmode=require."""
#     cmd = host.run(
#         'PGPASSWORD=testpassword psql '
#         '"host=127.0.0.1 port=6432 user=testuser dbname=testdb sslmode=require" '
#         "-c 'SELECT 1;'"
#     )
#     assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


# def test_pgbouncer_tls_connection_with_verify_ca(host):
#     """Verify PGBouncer accepts TLS connections with CA verification."""
#     cmd = host.run(
#         'PGPASSWORD=testpassword psql '
#         '"host=127.0.0.1 port=6432 user=testuser dbname=testdb '
#         'sslmode=verify-ca sslrootcert=/etc/pgbouncer/tls/ca.crt" '
#         "-c 'SELECT 1;'"
#     )
#     assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


# def test_pgbouncer_connection_without_tls_fails(host):
#     """Verify PGBouncer rejects non-TLS connections when TLS is required."""
#     cmd = host.run(
#         'PGPASSWORD=testpassword psql '
#         '"host=127.0.0.1 port=6432 user=testuser dbname=testdb sslmode=disable" '
#         "-c 'SELECT 1;'"
#     )
#     # Connection should fail when TLS is required
#     assert cmd.rc != 0, "Connection without TLS should be rejected"


# def test_postgresql_direct_tls_connection(host):
#     """Verify PostgreSQL accepts direct TLS connections."""
#     cmd = host.run(
#         'PGPASSWORD=testpassword psql '
#         '"host=127.0.0.1 port=5432 user=testuser dbname=testdb sslmode=require" '
#         "-c 'SELECT 1;'"
#     )
#     assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"


# def test_full_tls_chain_query(host):
#     """Verify full TLS chain works: client -> PGBouncer (TLS) -> PostgreSQL (TLS)."""
#     # Execute a query through PGBouncer with TLS and verify it works
#     cmd = host.run(
#         'PGPASSWORD=testpassword psql '
#         '"host=127.0.0.1 port=6432 user=testuser dbname=testdb '
#         'sslmode=verify-ca sslrootcert=/etc/pgbouncer/tls/ca.crt" '
#         "-c 'SELECT current_database();' -t -A"
#     )
#     assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"
#     assert "testdb" in cmd.stdout, f"Expected 'testdb' in output, got: {cmd.stdout}"