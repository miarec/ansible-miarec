"""Web tier: Apache, miarecweb, and live monitoring. No Celery."""
import json
import os
from conftest import hosts_in, peer_ip, PGBOUNCER_PORT, REDIS_PORT

testinfra_hosts = hosts_in('web')

miarecweb_version = os.environ.get('MIARECWEB_VERSION')
miarec_livemon_version = os.environ.get('MIAREC_LIVEMON_VERSION')


def test_directories(host):
    for dir in [
        "/opt/miarecweb/releases/{}".format(miarecweb_version),
        "/opt/miarec_livemon/releases/{}".format(miarec_livemon_version),
        "/var/log/miarec_livemon",
    ]:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_service(host):
    apache = "apache2" if host.system_info.distribution == "ubuntu" else "httpd"
    for service in [apache, "miarec_livemon"]:
        s = host.service(service)
        assert s.is_enabled, f"Service {service} is not enabled"
        assert s.is_running, f"Service {service} is not running"


def test_no_celery(host):
    for path in ["/etc/systemd/system/celeryd.service", "/etc/systemd/system/celerybeat.service"]:
        assert not host.file(path).exists, f"{path} must not exist on the web host"


def test_socket(host):
    for socket in ["tcp://0.0.0.0:80", "tcp://0.0.0.0:443", "tcp://0.0.0.0:6087"]:
        assert host.socket(socket).is_listening, f"Socket {socket} is not listening"


def test_production_ini_points_to_peers(host):
    ini = host.file("/opt/miarecweb/releases/{}/production.ini".format(miarecweb_version))
    assert ini.exists
    db_ip = peer_ip(host, 'db')
    redis_ip = peer_ip(host, 'redis')
    assert ini.contains(f"^DATABASE_HOST = {db_ip}$")
    assert ini.contains(f"^DATABASE_PORT = {PGBOUNCER_PORT}$")
    assert ini.contains(f"^REDIS_HOST = {redis_ip}$")
    assert ini.contains(f"^REDIS_PORT = {REDIS_PORT}$")


def test_health_endpoint(host):
    """The web application reaches PostgreSQL and Redis on their hosts."""
    result = host.run("curl -fsSLk http://localhost/health")
    assert result.rc == 0, f"Health endpoint not reachable: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("postgresql") == "ok", f"Unexpected PostgreSQL status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"


def test_script(host):
    result = host.run("/opt/miarecweb/current/pyenv/bin/python -m miarecweb.scripts.create_root_user -u admin -p admin")
    assert result.rc == 0 or "already exists" in result.stderr, f"Miarecweb script failed: {result.stderr}"
