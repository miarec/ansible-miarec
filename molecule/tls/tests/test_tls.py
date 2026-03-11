import json
import os
import pytest
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ["MOLECULE_INVENTORY_FILE"]
).get_hosts("all")


@pytest.fixture(scope="module")
def tls_paths():
    return {
        "pg": {
            "cert": "/etc/postgresql/tls/server.crt",
            "key": "/etc/postgresql/tls/server.key",
            "ca": "/etc/postgresql/tls/ca.crt",
        },
        "pgbouncer": {
            "cert": "/etc/pgbouncer/tls/server.crt",
            "key": "/etc/pgbouncer/tls/server.key",
            "client_cert": "/etc/pgbouncer/tls/client.crt",
            "client_key": "/etc/pgbouncer/tls/client.key",
            "ca": "/etc/pgbouncer/tls/ca.crt",
        },
        "redis": {
            "cert": "/etc/redis/tls/server.crt",
            "key": "/etc/redis/tls/server.key",
            "ca": "/etc/redis/tls/ca.crt",
        },
        "miarecweb_db": "/opt/miarecweb/current/production.ini",
        "miarec_ini": "/opt/miarec/current/miarec.ini",
    }


def test_postgresql_tls_files(host, tls_paths):
    for path in tls_paths["pg"].values():
        f = host.file(path)
        assert f.exists, f"{path} missing"
        assert f.user == "postgres"


def test_postgresql_tls_only(host):
    cmd = (
        "PGPASSWORD=password "
        "PGSSLMODE=verify-ca "
        "PGSSLROOTCERT=/etc/postgresql/tls/ca.crt "
        "PGSSLCERT=/etc/postgresql/tls/client.crt "
        "PGSSLKEY=/etc/postgresql/tls/client.key "
        "psql -h 127.0.0.1 -U miarec -d miarecdb -c 'SELECT 1'"
    )
    result = host.run(cmd)
    assert result.rc == 0, result.stderr

    no_tls = host.run(
        "PGPASSWORD=password PGSSLMODE=disable "
        "psql -h 127.0.0.1 -U miarec -d miarecdb -c 'SELECT 1'"
    )
    assert no_tls.rc != 0, "Non-TLS connection unexpectedly succeeded"


def test_pgbouncer_tls_config(host):
    conf = host.file("/etc/pgbouncer/pgbouncer.ini")
    assert conf.contains("client_tls_sslmode = require")
    assert conf.contains("server_tls_sslmode = verify-ca")


def test_pgbouncer_tls_only(host):
    cmd = (
        "PGPASSWORD=password "
        "PGSSLMODE=verify-ca "
        "PGSSLROOTCERT=/etc/pgbouncer/tls/ca.crt "
        "PGSSLCERT=/etc/pgbouncer/tls/client.crt "
        "PGSSLKEY=/etc/pgbouncer/tls/client.key "
        "psql -h 127.0.0.1 -p 6432 -U miarec -d miarecdb -c 'SELECT 1'"
    )
    result = host.run(cmd)
    assert result.rc == 0, result.stderr

    no_tls = host.run(
        "PGPASSWORD=password PGSSLMODE=disable "
        "psql -h 127.0.0.1 -p 6432 -U miarec -d miarecdb -c 'SELECT 1'"
    )
    assert no_tls.rc != 0, "Plaintext PGBouncer connection should fail"


def test_redis_tls_only(host):
    tls = host.run(
        "redis-cli --tls "
        "--cacert /etc/redis/tls/ca.crt "
        "--cert /etc/redis/tls/client.crt "
        "--key /etc/redis/tls/client.key "
        "PING"
    )
    assert tls.rc == 0 and "PONG" in tls.stdout

    no_tls = host.run("redis-cli PING")
    assert no_tls.rc != 0, "Plaintext Redis connection should fail"


def test_miarecweb_tls_config(host):
    ini = host.file("/opt/miarecweb/current/production.ini")
    assert "DATABASE_SSL_PARAMS" in ini.content_string
    assert "REDIS_SCHEMA = rediss" in ini.content_string


def test_miarec_recorder_tls_config(host):
    ini = host.file("/opt/miarec/current/miarec.ini")
    assert "SSLCertificate" in ini.content_string
    assert "SSLCACertificates" in ini.content_string


def test_miarec_service_running(host):
    service = host.service("miarec")
    assert service.is_enabled, "MiaRec service is not enabled"
    assert service.is_running, "MiaRec service is not running"


def test_miarecweb_services_running(host):
    services = ["apache2", "celeryd", "celerybeat"]
    for name in services:
        svc = host.service(name)
        assert svc.is_enabled, f"{name} service is not enabled"
        assert svc.is_running, f"{name} service is not running"


def test_miarecweb_health_endpoint(host):
    """Ensure MiaRecWeb /health reports healthy dependencies."""
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


def test_miarec_health_endpoint(host):
    """Verify MiaRec Recorder REST health endpoint is OK."""
    result = host.run("curl -fsS http://localhost:6088/health")
    assert result.rc == 0, f"Recorder health endpoint not reachable: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload.get("status") == "ok", f"Recorder status unexpected: {payload}"
    assert payload.get("database") == "ok", f"Recorder DB status unexpected: {payload}"
    assert payload.get("redis") == "ok", f"Recorder Redis status unexpected: {payload}"
