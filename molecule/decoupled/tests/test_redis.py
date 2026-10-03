"""Redis tier: Redis alone. No PostgreSQL, no PGBouncer."""
from conftest import hosts_in, listening_on_all_interfaces, PGBOUNCER_PORT, REDIS_PORT

testinfra_hosts = hosts_in('redis')


def test_directories(host):
    d = host.file("/var/log/redis")
    assert d.exists and d.is_directory, "Directory /var/log/redis does not exist"


def test_service(host):
    service = "redis-server" if host.system_info.distribution == "ubuntu" else "redis"
    s = host.service(service)
    assert s.is_enabled, f"Service {service} is not enabled"
    assert s.is_running, f"Service {service} is not running"


def test_socket(host):
    # Redis serves the other tiers.
    assert listening_on_all_interfaces(host, REDIS_PORT), "Redis does not listen on all interfaces"


def test_redis_bind(host):
    if host.system_info.distribution == "ubuntu":
        redis_conf = "/etc/redis/redis.conf"
    elif int(host.system_info.release.split(".")[0]) >= 9:
        redis_conf = "/etc/redis/redis.conf"
    else:
        redis_conf = "/etc/redis.conf"
    conf = host.file(redis_conf)
    assert conf.exists
    assert conf.contains(r"^bind 0\.0\.0\.0"), "Redis must bind to all interfaces"


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
