import json
import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

miarecweb_version = os.environ.get('MIARECWEB_VERSION')


def test_tls_certificates_exist(host):
    """Verify TLS certificates were generated."""
    cert_files = [
        # CA and client certs in /etc/miarecweb/tls/
        "/etc/miarecweb/tls/ca.crt",
        "/etc/miarecweb/tls/client.crt",
        "/etc/miarecweb/tls/client.key",
        # PostgreSQL server certs in /etc/postgresql/tls/
        "/etc/postgresql/tls/server.crt",
        "/etc/postgresql/tls/server.key",
        "/etc/postgresql/tls/ca.crt",
        # Redis server certs in /etc/redis/tls/
        "/etc/redis/tls/server.crt",
        "/etc/redis/tls/server.key",
        "/etc/redis/tls/ca.crt",
    ]
    for cert_file in cert_files:
        f = host.file(cert_file)
        assert f.exists, f"Certificate file not found: {cert_file}"
        assert f.is_file, f"Not a file: {cert_file}"


def test_production_ini_db_ssl_params(host):
    """Verify DATABASE_SSL_PARAMS is configured in production.ini."""
    ini_file = host.file(
        f"/opt/miarecweb/releases/{miarecweb_version}/production.ini"
    )
    assert ini_file.exists, "production.ini not found"

    content = ini_file.content_string
    assert "DATABASE_SSL_PARAMS" in content, "DATABASE_SSL_PARAMS not found in production.ini"
    assert "sslmode=verify-ca" in content, "sslmode not configured correctly"
    assert "sslrootcert=/etc/miarecweb/tls/ca.crt" in content, "sslrootcert not configured"
    assert "sslcert=/etc/miarecweb/tls/client.crt" in content, "sslcert not configured"
    assert "sslkey=/etc/miarecweb/tls/client.key" in content, "sslkey not configured"


def test_production_ini_redis_ssl_params(host):
    """Verify Redis TLS settings are configured in production.ini."""
    ini_file = host.file(
        f"/opt/miarecweb/releases/{miarecweb_version}/production.ini"
    )
    assert ini_file.exists, "production.ini not found"

    content = ini_file.content_string
    assert "REDIS_SCHEMA" in content, "REDIS_SCHEMA not found in production.ini"
    assert "rediss" in content, "Redis TLS schema (rediss) not configured"
    assert "REDIS_SSL_PARAMS" in content, "REDIS_SSL_PARAMS not found in production.ini"
    assert "ssl_ca_certs=/etc/miarecweb/tls/redis-ca.crt" in content, "ssl_ca_certs not configured"
    assert "ssl_certfile=/etc/miarecweb/tls/redis-client.crt" in content, "ssl_certfile not configured"
    assert "ssl_keyfile=/etc/miarecweb/tls/redis-client.key" in content, "ssl_keyfile not configured"


def test_postgresql_ssl_enabled(host):
    """Verify PostgreSQL has SSL enabled."""
    result = host.run(
        "sudo -u postgres psql -tAc \"SHOW ssl;\""
    )
    assert result.rc == 0, f"Failed to query PostgreSQL: {result.stderr}"
    assert "on" in result.stdout, "PostgreSQL SSL is not enabled"


def test_redis_tls_listening(host):
    """Verify Redis is listening on TLS port."""
    socket = host.socket("tcp://127.0.0.1:6379")
    assert socket.is_listening, "Redis is not listening on TLS port 6379"


def test_directories(host):
    """Verify required directories exist."""
    dirs = [
        f"/opt/miarecweb/releases/{miarecweb_version}",
        "/var/log/miarecweb",
        "/var/log/miarecweb/celery"
    ]
    for dir_path in dirs:
        d = host.file(dir_path)
        assert d.is_directory, f"Directory not found: {dir_path}"
        assert d.exists, f"Directory does not exist: {dir_path}"


def test_files(host):
    """Verify required files exist."""
    files = [
        f"/opt/miarecweb/releases/{miarecweb_version}/production.ini",
        "/etc/systemd/system/celerybeat.service",
        "/etc/systemd/system/celeryd.service",
    ]
    for file_path in files:
        f = host.file(file_path)
        assert f.exists, f"File not found: {file_path}"
        assert f.is_file, f"Not a file: {file_path}"


def test_services(host):
    """Verify services are enabled and running."""
    if host.system_info.distribution == "ubuntu":
        services = ["apache2", "celeryd", "celerybeat"]
    else:
        services = ["httpd", "celeryd", "celerybeat"]

    for service in services:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_health_endpoint(host):
    """Verify /health endpoint returns healthy status for dependencies."""
    result = host.run("curl -sSLk -w '\\n%{http_code}' http://localhost/health")
    assert result.rc == 0, f"Health endpoint curl failed (rc={result.rc}): {result.stderr}"

    output_lines = result.stdout.splitlines()
    assert output_lines, "Health endpoint returned no output"

    status_line = output_lines[-1]
    body = "\n".join(output_lines[:-1])

    try:
        http_status = int(status_line)
    except ValueError as exc:
        raise AssertionError(
            f"Could not parse HTTP status from health response: {status_line}\n"
            f"Full response:\n{result.stdout}\nStderr:\n{result.stderr}"
        ) from exc

    if http_status != 200:
        raise AssertionError(
            f"Health endpoint returned HTTP {http_status}\n"
            f"Body:\n{body or '<empty>'}\nStderr:\n{result.stderr}"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Health endpoint response is not valid JSON: {exc}\nResponse: {body}"
        )

    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("postgresql") == "ok", f"Unexpected PostgreSQL status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"


def test_alembic_with_tls(host):
    """Verify alembic can connect to PostgreSQL with TLS (via environment variables)."""
    # This works because upgrade_db.yml passes PGSSLMODE/PGSSLCERT/PGSSLKEY
    # as environment variables to alembic commands
    result = host.run(
        "PGSSLMODE=verify-ca "
        "PGSSLCERT=/etc/miarecweb/tls/client.crt "
        "PGSSLKEY=/etc/miarecweb/tls/client.key "
        "PGSSLROOTCERT=/etc/miarecweb/tls/ca.crt "
        "/opt/miarecweb/current/pyenv/bin/alembic -c /opt/miarecweb/current/production.ini current"
    )
    assert result.rc == 0, f"Alembic failed to connect with TLS: {result.stderr}"
    assert "(head)" in result.stdout or "head" in result.stdout.lower(), \
        f"Database not at head revision: {result.stdout}"