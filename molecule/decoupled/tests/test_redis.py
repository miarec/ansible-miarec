"""Redis tier: Redis alone. No PostgreSQL, no PGBouncer."""
import pytest
from conftest import hosts_in, listening_on_all_interfaces, TLS, PGBOUNCER_PORT, REDIS_PORT

testinfra_hosts = hosts_in('redis')


def redis_service(host):
    if host.run("systemctl cat %s", f"redis_{REDIS_PORT}").rc == 0:
        # Redis built from source (decoupled-tls on EL 7 and 8)
        return f"redis_{REDIS_PORT}"
    return "redis-server" if host.system_info.distribution == "ubuntu" else "redis"


def redis_conf(host):
    # Ubuntu and EL 9 packages, EL 7 and 8 packages, source build
    for path in ["/etc/redis/redis.conf", "/etc/redis.conf", "/opt/redis/redis.conf"]:
        if host.file(path).exists:
            return host.file(path)
    raise AssertionError("Redis configuration file not found")


def test_directories(host):
    d = host.file("/var/log/redis")
    assert d.exists and d.is_directory, "Directory /var/log/redis does not exist"


def test_service(host):
    service = redis_service(host)
    s = host.service(service)
    assert s.is_enabled, f"Service {service} is not enabled"
    assert s.is_running, f"Service {service} is not running"


def test_socket(host):
    # Redis serves the other tiers.
    assert listening_on_all_interfaces(host, REDIS_PORT), "Redis does not listen on all interfaces"


def test_redis_bind(host):
    assert redis_conf(host).contains(r"^bind 0\.0\.0\.0"), "Redis must bind to all interfaces"


def test_redis_tls_config(host):
    """With TLS, Redis accepts TLS connections with a trusted client certificate only.

    The Celery tests connect over the network with and without TLS.
    """
    conf = redis_conf(host)
    assert conf.contains(r"^port 0$") == TLS, "Redis must not accept plaintext connections with TLS"
    assert conf.contains(rf"^tls-port {REDIS_PORT}$") == TLS
    assert conf.contains(r"^tls-auth-clients yes$") == TLS


@pytest.mark.skipif(TLS, reason="This host has no client certificate. The Celery tests send PING over TLS.")
def test_redis_ping(host):
    """Redis accepts connections and answers commands."""
    result = host.run("redis-cli PING")
    assert result.rc == 0, f"redis-cli PING failed: {result.stderr}"
    assert result.stdout.strip() == "PONG", f"Unexpected reply: {result.stdout}"


def test_no_database(host):
    """PostgreSQL and PGBouncer run on the database host."""
    assert not host.socket("tcp://127.0.0.1:5432").is_listening
    assert not listening_on_all_interfaces(host, PGBOUNCER_PORT)
    assert not host.file("/etc/pgbouncer").exists, "PGBouncer must not be installed on the Redis host"


def test_no_application_tiers(host):
    """The Redis host carries no application."""
    for path in ["/opt/miarecweb", "/opt/miarec", "/opt/miarec_screen"]:
        assert not host.file(path).exists, f"{path} must not exist on the Redis host"
