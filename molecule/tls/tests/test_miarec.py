"""Test TLS configuration for MiaRec."""
import json
import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_miarec_service_running(host):
    """Test that miarec service is running."""
    service = host.service('miarec')
    assert service.is_running
    assert service.is_enabled


def test_miarec_ini_has_tls_settings(host):
    """Test that miarec.ini contains TLS settings."""
    ini_file = host.file('/opt/miarec/current/miarec.ini')
    assert ini_file.exists
    content = ini_file.content_string

    # Check PostgreSQL TLS settings
    assert 'UseSSL=true' in content or 'UseSSL = true' in content
    assert 'SSLCACertificates' in content
    assert 'SSLCertificate' in content
    assert 'SSLPrivateKey' in content


def test_tls_certificate_files_exist(host):
    """Test that TLS certificate files exist with correct permissions."""
    ca_file = host.file('/etc/miarec/tls/ca.crt')
    assert ca_file.exists
    assert ca_file.mode == 0o644

    client_cert = host.file('/etc/miarec/tls/client.crt')
    assert client_cert.exists
    assert client_cert.mode == 0o644

    client_key = host.file('/etc/miarec/tls/client.key')
    assert client_key.exists
    assert client_key.mode == 0o640
    assert client_key.group == 'miarec'


def test_health_endpoint(host):
    """Verify /health endpoint returns healthy status for TLS connections."""
    # MiaRec REST API listens on port 6088
    result = host.run("curl -fsS http://localhost:6088/health")
    assert result.rc == 0, f"Health endpoint not reachable: {result.stderr}"

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Health endpoint response is not valid JSON: {exc}\n"
            f"Response: {result.stdout}"
        )

    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("database") == "ok", f"Database TLS connection failed: {payload}"
    assert payload.get("redis") == "ok", f"Redis TLS connection failed: {payload}"