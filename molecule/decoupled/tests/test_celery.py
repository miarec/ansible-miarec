"""Celery tier: worker and beat. No Apache."""
import os
from conftest import hosts_in, peer_ip, process_owners, DB_NAME, DB_USER, DB_PASSWORD, PGBOUNCER_PORT, REDIS_PORT

testinfra_hosts = hosts_in('celery')

miarecweb_version = os.environ.get('MIARECWEB_VERSION')


def test_directories(host):
    for dir in [
        "/opt/miarecweb/releases/{}".format(miarecweb_version),
        "/var/log/miarecweb",
        "/var/log/miarecweb/celery",
    ]:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_files(host):
    for file in [
        "/etc/systemd/system/celerybeat.service",
        "/etc/systemd/system/celeryd.service",
        "/var/log/miarecweb/celery/beat.log",
        "/var/log/miarecweb/celery/worker1.log",
    ]:
        f = host.file(file)
        assert f.exists and f.is_file, f"File {file} does not exist"


def test_service(host):
    for service in ["celeryd", "celerybeat"]:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_process_user(host):
    """The Celery worker and beat run as the celery user in the miarec group."""
    assert process_owners(host, "celery") == {("celery", "miarec")}


def test_no_apache(host):
    apache = "apache2" if host.system_info.distribution == "ubuntu" else "httpd"
    assert not host.exists(apache), f"{apache} must not be installed on the Celery host"
    assert not host.socket("tcp://0.0.0.0:80").is_listening


def test_production_ini_points_to_peers(host):
    ini = host.file("/opt/miarecweb/releases/{}/production.ini".format(miarecweb_version))
    assert ini.exists
    db_ip = peer_ip(host, 'db')
    redis_ip = peer_ip(host, 'redis')
    assert ini.contains(f"^DATABASE_HOST = {db_ip}$")
    assert ini.contains(f"^REDIS_HOST = {redis_ip}$")


def test_database_connection(host):
    """The Celery host authenticates against PGBouncer on the database host."""
    db_ip = peer_ip(host, 'db')
    cmd = (
        "/opt/miarecweb/current/pyenv/bin/python -c \""
        "import psycopg2; "
        f"c = psycopg2.connect(host='{db_ip}', port={PGBOUNCER_PORT}, dbname='{DB_NAME}', user='{DB_USER}', password='{DB_PASSWORD}', connect_timeout=5); "
        "cur = c.cursor(); cur.execute('SELECT 1'); print(cur.fetchone()[0])\""
    )
    result = host.run(cmd)
    assert result.rc == 0, f"Database connection failed: {result.stderr}"
    assert result.stdout.strip() == "1"


def test_redis_connection(host):
    """The Celery host reaches Redis on the Redis host."""
    redis_ip = peer_ip(host, 'redis')
    cmd = (
        "/opt/miarecweb/current/pyenv/bin/python -c \""
        "import redis; "
        f"print(redis.Redis(host='{redis_ip}', port={REDIS_PORT}, socket_connect_timeout=5).ping())\""
    )
    result = host.run(cmd)
    assert result.rc == 0, f"Redis connection failed: {result.stderr}"
    assert result.stdout.strip() == "True"
