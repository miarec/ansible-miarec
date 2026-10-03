"""Screen tier: the screen recording controller alone."""
import os
from conftest import hosts_in, peer_ip, PGBOUNCER_PORT, REDIS_PORT

testinfra_hosts = hosts_in('screen')

miarec_screen_version = os.environ.get('MIAREC_SCREEN_VERSION')


def test_directories(host):
    for dir in [
        "/opt/miarec_screen/releases/{}".format(miarec_screen_version),
        "/opt/miarec_screen/shared",
        "/var/log/miarec_screen",
    ]:
        d = host.file(dir)
        assert d.exists and d.is_directory, f"Directory {dir} does not exist"


def test_service(host):
    s = host.service("miarec_screen")
    assert s.is_enabled
    assert s.is_running


def test_socket(host):
    for socket in ["tcp://0.0.0.0:6089", "tcp://0.0.0.0:6091", "tcp://0.0.0.0:6092"]:
        assert host.socket(socket).is_listening, f"Socket {socket} is not listening"


def test_ini_points_to_peers(host):
    ini = host.file("/opt/miarec_screen/releases/{}/miarec_screen.ini".format(miarec_screen_version))
    assert ini.exists
    db_ip = peer_ip(host, 'db')
    redis_ip = peer_ip(host, 'redis')
    web_ip = peer_ip(host, 'web')
    celery_ip = peer_ip(host, 'celery')
    content = ini.content_string
    assert f"Host = {db_ip}:{PGBOUNCER_PORT}" in content
    assert f"Host = {redis_ip}:{REDIS_PORT}" in content
    assert ini.contains(rf"^IpAddress = 127\.0\.0\.1;.*\b{web_ip}\b")
    assert ini.contains(rf"^IpAddress = 127\.0\.0\.1;.*\b{celery_ip}\b")


def test_no_recorder(host):
    assert not host.file("/opt/miarec").exists, "The call recorder must not exist on the screen host"
