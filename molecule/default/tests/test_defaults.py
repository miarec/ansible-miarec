"""Infrastructure tests for PostgreSQL, PGBouncer, and Redis."""
import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

postgresql_version = os.environ.get('POSTGRESQL_VERSION')


def test_directories(host):
    """Test that infrastructure directories exist."""
    if host.system_info.distribution == "ubuntu":
        postgresql_dir = "/etc/postgresql/{}".format(postgresql_version)
    else:
        postgresql_dir = "/var/lib/pgsql/{}/data".format(postgresql_version)

    dirs = [
        postgresql_dir,
        "/var/log/pgbouncer",
        "/var/log/redis",
    ]
    for dir in dirs:
        d = host.file(dir)
        assert d.is_directory, f"Directory {dir} does not exist"
        assert d.exists


def test_files(host):
    """Test that infrastructure config files exist."""
    if host.system_info.distribution == "ubuntu":
        postgresql_conf = "/etc/postgresql/{}/main/postgresql.conf".format(postgresql_version)
        redis_conf = "/etc/redis/redis.conf"
    else:
        postgresql_conf = "/var/lib/pgsql/{}/data/postgresql.conf".format(postgresql_version)
        redis_conf = "/etc/redis.conf"

    files = [
        postgresql_conf,
        redis_conf,
        "/etc/pgbouncer/pgbouncer.ini",
    ]

    for file in files:
        f = host.file(file)
        assert f.exists, f"File {file} does not exist"
        assert f.is_file


def test_service(host):
    """Test that infrastructure services are running."""
    if host.system_info.distribution == "ubuntu":
        postgresql_service = "postgresql"
        redis_service = "redis-server"
    else:
        postgresql_service = "postgresql-{}".format(postgresql_version)
        redis_service = "redis"

    services = [
        postgresql_service,
        redis_service,
        "pgbouncer",
    ]

    for service in services:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_socket(host):
    """Test that infrastructure services are listening on expected ports."""
    sockets = [
        "tcp://127.0.0.1:5432",   # PostgreSQL
        "tcp://127.0.0.1:6432",   # PGBouncer
        "tcp://127.0.0.1:6379",   # Redis
    ]
    for socket in sockets:
        s = host.socket(socket)
        assert s.is_listening, f"Socket {socket} is not listening"
