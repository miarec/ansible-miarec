"""Test TLS configuration for the MiaRec screen recording controller."""
import json
import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']
).get_hosts('all')


def test_miarec_screen_service_running(host):
    service = host.service('miarec_screen')
    assert service.is_running
    assert service.is_enabled


def test_miarec_screen_ini_has_tls_settings(host):
    """The screen controller uses the recorder's TLS files for PostgreSQL and Redis."""
    content = host.file('/opt/miarec_screen/current/miarec_screen.ini').content_string
    for setting in [
        'SSLCACertificates = /etc/miarec/tls/ca.crt',
        'SSLCertificate = /etc/miarec/tls/client.crt',
        'SSLPrivateKey = /etc/miarec/tls/client.key',
        'SSLCACertificates = /etc/miarec/tls/redis-ca.crt',
        'SSLCertificate = /etc/miarec/tls/redis-client.crt',
        'SSLPrivateKey = /etc/miarec/tls/redis-client.key',
    ]:
        assert setting in content, f"{setting} not found in miarec_screen.ini"
    assert content.count('UseSSL = true') == 2, "UseSSL must be on in [Database] and [RedisSubscriber]"


def test_health_endpoint(host):
    """The screen controller reaches PostgreSQL and Redis over TLS.

    PGBouncer and Redis reject plaintext connections, so "ok" proves TLS.
    """
    # The REST API of the screen controller listens on port 6089
    result = host.run("curl -fsS http://localhost:6089/health")
    assert result.rc == 0, f"Health endpoint not reachable: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("database") == "ok", f"Database TLS connection failed: {payload}"
    assert payload.get("redis") == "ok", f"Redis TLS connection failed: {payload}"
