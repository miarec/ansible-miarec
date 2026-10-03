"""Recorder tier: the call recorder alone."""
import json
import os
from conftest import runner, hosts_in, peer_ip, PGBOUNCER_PORT, REDIS_PORT

testinfra_hosts = hosts_in('recorder')

miarec_version = os.environ.get('MIAREC_VERSION')


def test_directories(host):
    for dir in [
        "/opt/miarec/releases/{}".format(miarec_version),
        "/opt/miarec/shared",
        "/var/log/miarec",
        "/var/log/miarec/cdr",
        "/var/log/miarec/error",
        "/var/log/miarec/trace",
        "/var/miarec/recordings",
    ]:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_service(host):
    s = host.service("miarec")
    assert s.is_enabled
    assert s.is_running


def test_socket(host):
    for socket in ["tcp://0.0.0.0:9080", "tcp://0.0.0.0:5080", "tcp://0.0.0.0:6554", "tcp://0.0.0.0:6088"]:
        assert host.socket(socket).is_listening, f"Socket {socket} is not listening"


def test_ini_points_to_peers(host):
    ini = host.file("/opt/miarec/releases/{}/miarec.ini".format(miarec_version))
    assert ini.exists
    db_ip = peer_ip(host, 'db')
    redis_ip = peer_ip(host, 'redis')
    web_ip = peer_ip(host, 'web')
    celery_ip = peer_ip(host, 'celery')
    content = ini.content_string
    assert f"Host = {db_ip}:{PGBOUNCER_PORT}" in content
    assert f"Host = {redis_ip}:{REDIS_PORT}" in content
    assert f"http://{web_ip}/notify/call" in content
    # The web and Celery hosts may call the recorder REST API.
    assert ini.contains(rf"^IpAddress = 127\.0\.0\.1;.*\b{web_ip}\b")
    assert ini.contains(rf"^IpAddress = 127\.0\.0\.1;.*\b{celery_ip}\b")


def test_health_endpoint(host):
    """The recorder reaches PostgreSQL and Redis on their hosts.

    The recorder image has no curl, so the web host queries the REST API over
    the network. That also proves the web host is on the API allow-list.
    """
    rec_ip = peer_ip(host, 'recorder')
    web_host = runner.get_host(hosts_in('web')[0])
    result = web_host.run(f"curl -fsS --max-time 10 http://{rec_ip}:6088/health")
    assert result.rc == 0, f"Health endpoint not reachable from the web host: {result.stderr}"
    payload = json.loads(result.stdout)
    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("database") == "ok", f"Unexpected database status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"
