import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')


def test_redis_service_running(host):
    """Verify Redis service is enabled and running."""
    if host.system_info.distribution == "ubuntu":
        s = host.service("redis-server")
    else:
        s = host.service("redis")
    assert s.is_enabled
    assert s.is_running


def test_redis_tls_port_listening(host):
    """Verify Redis is listening on TLS port."""
    s = host.socket("tcp://127.0.0.1:6379")
    assert s.is_listening


def test_redis_tls_connection_with_valid_certs(host):
    """Verify Redis accepts TLS connections with valid CA-signed certificates."""
    cmd = host.run(
        "redis-cli --tls "
        "--cert /etc/redis/tls/client.crt "
        "--key /etc/redis/tls/client.key "
        "--cacert /etc/redis/tls/ca.crt "
        "PING"
    )
    assert cmd.rc == 0, f"Expected rc=0, got rc={cmd.rc}, stderr={cmd.stderr}"
    assert "PONG" in cmd.stdout


def test_redis_connection_without_tls_fails(host):
    """Verify Redis rejects non-TLS connections."""
    cmd = host.run("redis-cli PING")
    # Connection should fail when TLS is required
    assert cmd.rc != 0 or "PONG" not in cmd.stdout


def test_redis_tls_connection_with_invalid_cert_fails(host):
    """Verify Redis rejects TLS connections with certificates not signed by CA."""
    cmd = host.run(
        "redis-cli --tls "
        "--cert /etc/redis/tls/invalid-client.crt "
        "--key /etc/redis/tls/invalid-client.key "
        "--cacert /etc/redis/tls/ca.crt "
        "PING"
    )
    # Connection should fail with invalid certificate
    assert cmd.rc != 0 or "PONG" not in cmd.stdout