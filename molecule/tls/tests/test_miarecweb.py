import json
import os
import testinfra.utils.ansible_runner

testinfra_hosts = testinfra.utils.ansible_runner.AnsibleRunner(
    os.environ['MOLECULE_INVENTORY_FILE']).get_hosts('all')

miarecweb_version = os.environ.get('MIARECWEB_VERSION')


def test_directories(host):

    dirs = [
        "/opt/miarecweb/releases/{}".format(miarecweb_version),
        "/var/log/miarecweb",
        "/var/log/miarecweb/celery"
    ]
    for dir in dirs:
        d = host.file(dir)
        assert d.is_directory
        assert d.exists

def test_files(host):
    files = [
        "/opt/miarecweb/releases/{}/production.ini".format(miarecweb_version),
        "/etc/systemd/system/celerybeat.service",
        "/etc/systemd/system/celeryd.service",
        "/var/log/miarecweb/celery/beat.log",
        "/var/log/miarecweb/celery/worker1.log"
    ]

    for file in files:
        f = host.file(file)
        assert f.exists
        assert f.is_file

def test_service(host):
    if host.system_info.distribution == "ubuntu":
        services = [
            "celeryd",
            "celerybeat",
            "apache2"
        ]

    else:
        services = [
            "celeryd",
            "celerybeat",
            "httpd"
        ]

    for service in services:
        s = host.service(service)
        assert s.is_enabled
        assert s.is_running

def test_socket(host):
    sockets = [
        "tcp://0.0.0.0:80",
        "tcp://0.0.0.0:443"
    ]
    for socket in sockets:
        s = host.socket(socket)
        assert s.is_listening


def test_health_endpoint(host):
    result = host.run("curl -fsSLk http://localhost/health")
    assert result.rc == 0, f"Health endpoint not reachable: {result.stderr}"

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Health endpoint response is not valid JSON: {exc}\nResponse: {result.stdout}")

    assert payload.get("status") == "ok", f"Unexpected overall status: {payload}"
    assert payload.get("postgresql") == "ok", f"Unexpected PostgreSQL status: {payload}"
    assert payload.get("redis") == "ok", f"Unexpected Redis status: {payload}"


def test_script(host):
    result = host.run("/opt/miarecweb/current/pyenv/bin/python -m miarecweb.scripts.create_root_user -u admin -p admin")
    # rc == 0: User created successfully
    # rc == 1 with "already exists": User already exists (idempotent - also success)
    assert result.rc == 0 or "already exists" in result.stderr, f"Miarecweb script failed: {result.stderr}"
